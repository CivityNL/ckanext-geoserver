from __future__ import absolute_import
from geoserver.support import url, DimensionInfo
from ckanext.geoserver.model.Geoserver import Geoserver
from ckanext.geoserver.model.Datastored import Datastored
from ckanext.geoserver.model.ShapeFile import Shapefile
from ckanext.geoserver.model.MultiDatastored import MultiDatastored
from ckanext.geoserver.model.MultiShapeFile import MultiShapeFile
from ckanext.geoserver.model.MultiRasterFile import MultiRasterFile
from ckanext.geoserver.model.RasterFile import RasterFile
from ckan.plugins import toolkit
from pylons import config
from lxml import etree, objectify
from StringIO import StringIO
import json
import urllib
import logging
import re
import ckanext.geoserver.misc.helpers as helpers


class Layer(object):
    """
    Creates an WFS and an WMS layer in Geoserver and updates the CKAN package dictionary with new resource
    information.  The class of the object instance is called first here instead of the object instance itself.  By
    calling the the class method without instantiating the class itself, we essentially create a subclass (not a
    parent class) via inheritance.
    """

    @classmethod
    def publish(cls, package_id, resource_id, workspace_name, layer_name, layer_version, username, geoserver, store=None, workspace=None, lat_field=None, lng_field=None, join_key=None):
        """
        Publishes a layer as WMS and WFS OGC services in Geoserver.  Calls the 'Layer' class before the object
        instance to make a subclass via inheritance.
        """
        layer = cls(package_id, resource_id, workspace_name, layer_name, layer_version, username, geoserver, store, workspace, lat_field, lng_field, join_key)
        # layer.publish_init()
        if layer.create():
            return layer
        else:
            return None

    @classmethod
    def unpublish(cls, geoserver, layer_name, resource_id, package_id, username):
        layer = cls(package_id, resource_id, None, layer_name, None, username, geoserver, None, None, None, None)
        if layer.remove():
            return True
        else:
            return False

    # Define properties of the object instance which will be passed into the class method
    def __init__(self, package_id, resource_id, workspace_name, layer_name, layer_version, username, geoserver, store=None, workspace=None, lat_field=None, lng_field=None, join_key=None):
        self.geoserver = Geoserver.from_ckan_config()
        self.name = layer_name
        self.layer_version = layer_version
        self.username = username
        if resource_id.endswith("_multi"):
            self.file_resource = toolkit.get_action("package_show")(None, {
                "id": package_id
                })
        else:
            self.file_resource = toolkit.get_action("resource_show")(None, {
                "id": resource_id
                })
        self.package_id = package_id
        self.resource_id = resource_id
        self.store = self.geoserver.get_datastore(workspace, store, workspace_name, layer_version)
        self.workspace_name = workspace_name
        self.join_key = join_key

        if not resource_id.endswith("_multi"):
            url_ = self.file_resource["url"]
            kwargs = {
                "resource_id": self.file_resource["id"]
                }
            # Determine whether to handle the data with shapefile or datastored csv operators
            if url_.endswith('.zip'):
                cls = Shapefile
            elif url_.endswith('.csv'):
                cls = Datastored
                kwargs.update({
                    "lat_field": lat_field,
                    "lng_field": lng_field
                    })
            elif url_.endswith('.tif'):
                cls = RasterFile
            else:
                # The resource cannot be spatialized
                raise Exception(toolkit._("Only CSV and Shapefile data can be spatialized"))
        else:
            kwargs = {
                "package_id": self.package_id
                }
            if resource_id == 'schema_descriptor_multi':
                cls = MultiDatastored
                kwargs.update({
                    "lat_field": lat_field,
                    "lng_field": lng_field,
                    "join_key": self.join_key
                    })
            elif resource_id == 'shapefile_multi':
                cls = MultiShapeFile
            elif resource_id == 'schema_descriptor_timeseries_multi':
                cls = MultiRasterFile
            else:
                # The resource cannot be spatialized
                raise Exception(toolkit._("Can not spatialize package."))

        # '**' unpacks the kwargs dictionary which can contain an arbitrary number of arguments
        self.data = cls(**kwargs)

    def create(self):
        """
        Creates the new layer to Geoserver and then creates the resources in Package(CKAN).
        """
        # Spatialize
        if not self.data.publish():
            # Spatialization failed
            raise Exception(toolkit._("Spatialization failed."))
        self.create_layer()
        self.create_geo_resources()
        self.add_sld_if_exists()

        return True

    def remove(self):
        """
        Removes the Layer from Geoserver and the geo resources from the pacakage.
        """

        ready = self.remove_layer()
        if ready:
            ready = self.remove_geo_resources()
            if ready:
                ready = self.data.unpublish()

        return ready

    def create_layer(self):
        """
        Constructs the layer details and creates it in the geoserver.
        If the layer already exists then return the pre-existing layer.
        Layer "existence" is based entirely on the layer's name -- it must be unique

        @returns geoserver layer
        """

        # If the layer already exists in Geoserver then return it
        if self.resource_id.endswith("_multi"):
            layer = self.geoserver.get_layer(self.getName())
        else:
            layer = self.geoserver.get_layer(self.name)
        layer_workspace_name = None
        if layer:
            layer_workspace_name = str(layer.resource._workspace).replace(' ', '').split('@')[0]

        if not layer or (layer_workspace_name and layer_workspace_name != self.workspace_name):

            if isinstance(self.data, RasterFile):
                ws = self.geoserver.default_workspace()
                resource = toolkit.get_action("resource_show")(None, {
                    "id": self.resource_id
                    })
                if resource.get("format", {}) == "geotiff":
                    url_ = resource.get("url", {})
                    label = url_.rsplit('/', 1)[-1]
                    self.geoserver.create_coveragestore_external_geotiff(self.getName(), "file:///var/tmp/GeoserverUpload/" + self.package_id + "/" + label, ws, overwrite=True)
                    layer = self.geoserver.get_layer(self.name)

            elif isinstance(self.data, MultiRasterFile):
                ws = self.geoserver.default_workspace()
                label = toolkit.get_action("package_show")(None, {
                    "id": self.package_id
                    }).get("name", self.package_id)

                self.geoserver.create_imagemosaic(self.getName(), self.data.zipFileLocation, workspace=ws, overwrite=True)

                coverage = self.geoserver.get_resource_by_url(ws.coveragestore_url.replace(".xml", "/" + self.getName() + "/coverages/" + self.getName() + ".xml"))

                coverage.supported_formats = ['GEOTIFF']
                coverage.title = label
                timeInfo = DimensionInfo("time", "true", "LIST", None, "ISO8601", None)
                coverage.metadata = ({
                    'dirName': self.getName() + "_" + self.getName(),
                    'time': timeInfo
                    })
                self.geoserver.save(coverage)
                layer = self.geoserver.get_layer(self.getName())
            else:
                # Construct layer creation request.
                feature_type_url = url(self.geoserver.service_url, ["workspaces", self.store.workspace.name, "datastores", self.store.name, "featuretypes"])

                if self.resource_id.endswith("_multi"):
                    description = self.file_resource["notes"]
                else:
                    description = self.file_resource["description"]

                data = {
                    "featureType": {
                        "name": self.getName(),
                        "nativeName": self.getName(),
                        "title": self.file_resource["name"],
                        "abstract": description
                        }
                    }

                request_headers = {
                    "Content-type": "application/json"
                    }

                response_headers, response = self.geoserver.http.request(feature_type_url, "POST", json.dumps(data), request_headers)
                if not "already exists in store" in response:
                    if not 200 <= response_headers.status < 300:
                        raise Exception(toolkit._("Geoserver layer creation failed: %i -- %s") % (response_headers.status, response))

                layer = self.geoserver.get_layer(self.name)
            return layer

        # Add the layer's name to the file resource
        self.file_resource.update({
            "layer_name": self.name
            })
        self.file_resource = toolkit.get_action("resource_patch")({
            "user": self.username
            }, self.file_resource)
        # Return the layer
        return layer

    def remove_layer(self):
        """
        Removes the layer from geoserver.
        """
        layer = self.geoserver.get_layer(self.getName())
        if layer:
            self.geoserver.delete(layer, purge=True, recurse=True)

        return True

    def create_geo_resources(self):
        """
        Creates the geo resources(WMS, WFS) into CKAN. Created layer can provide WMS and WFS capabilities.
        Gets the file resource details and creates two new resources for the package.

        Must hand in a CKAN user for creating things
        """

        context = {
            "user": self.username
            }

        def capabilities_url(service_url, workspace, layer, service, version):

            try:
                specifications = "/%s/ows?service=%s&version=%s&request=GetCapabilities#%s" % (workspace, service, version, layer)
                return service_url.replace("/rest", specifications)
            except:
                service = service.lower()
                specifications = "/" + service + "?request=GetCapabilities"
                return service_url.replace("/rest", specifications)

        # def ckanOGCServicesURL(serviceUrl):
        #     newServiceUrl = serviceUrl
        #     try:
        #         siteUrl = config.get('ckan.site_url', None)
        #
        #         if siteUrl:
        #             encodedURL = urllib.quote_plus(serviceUrl, '')
        #             newServiceUrl = siteUrl + "/geoserver/get-ogc-services?url=" + encodedURL + "&workspace=" + self.workspace_name
        #
        #     except:
        #         return serviceUrl
        #
        #     return newServiceUrl

        # WMS Resource Creation, layer: is important for ogcpreview ext used for WMS, and feature_type is used for WFS in ogcpreview ext
        data_dict = {
            'package_id': self.package_id,
            'parent_resource': self.file_resource['id'],
            'url': capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WMS', '1.1.1'),
            'description': 'WMS for %s' % self.file_resource[
                'name'],
            'distributor': self.file_resource.get("distributor", json.dumps({
                "name": "Unknown",
                "email": "unknown"
                })),
            'protocol': 'WMS',
            'format': 'WMS',
            'feature_type': "%s:%s" % (
                self.store.workspace.name, self.getName()),
            'layer': "%s" % self.getName(),
            'resource_format': 'data-service',
            'url_ogc': capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WMS', '1.1.1'),
            }
        self.wms_resource = toolkit.get_action('resource_create')(context, data_dict)

        if isinstance(self.data, RasterFile) or isinstance(self.data, MultiRasterFile):
            # WCS Resource Creation
            data_dict.update(
                {
                    "package_id": self.package_id,
                    'parent_resource': self.file_resource['id'],
                    "url": capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WCS', '1.1.1'),
                    "description": "WCS for %s" % self.file_resource[
                        "name"],
                    'distributor': self.file_resource.get("distributor", json.dumps({
                        "name": "Unknown",
                        "email": "unknown"
                        })),
                    "protocol": "WCS",
                    "format": "WCS",
                    "feature_type": "%s:%s" % (self.store.workspace.name, self.getName()),
                    'resource_format': 'data-service',
                    'url_ogc': capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WCS', '1.1.1')
                    })
            self.wcs_resource = toolkit.get_action('resource_create')(context, data_dict)

            # Return the two resource dicts
            return self.wms_resource, self.wcs_resource
        else:
            # WFS Resource Creation
            data_dict.update({
                "package_id": self.package_id,
                'parent_resource': self.file_resource['id'],
                "url": capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WFS', '1.1.0'),
                "description": "WFS for %s" % self.file_resource[
                    "name"],
                'distributor': self.file_resource.get("distributor", json.dumps({
                    "name": "Unknown",
                    "email": "unknown"
                    })),
                "protocol": "WFS",
                "format": "WFS",
                "feature_type": "%s:%s" % (
                    self.store.workspace.name, self.getName()),
                'resource_format': 'data-service',
                'url_ogc': capabilities_url(self.geoserver.service_url, self.store.workspace.name, self.getName(), 'WFS', '1.1.0'),
                })
            self.wfs_resource = toolkit.get_action('resource_create')(context, data_dict)

            # Return the two resource dicts
            return self.wms_resource, self.wfs_resource

    def remove_geo_resources(self):
        """
        Removes the list of resources from package. If the resources list not provided then find the geo resources based
        on parent_resource value and then removes them from package.
        """

        context = {
            "user": self.username
            }
        results = toolkit.get_action("resource_search")(context, {
            "query": "parent_resource:%s" % self.file_resource["id"]
            })
        for result in results.get("results", []):
            toolkit.get_action("resource_delete")(context, {
                "id": result["id"]
                })

        return True

    def add_sld_if_exists(self):
        """
        Checks if SLD was uploaded.
        Validates SLD according to SLD Standard 1.0.0
        Make some minor changes to SLD (lowercase columnnames, rename geom column to wkb_geometry)
        Add SLD to geoserver
        Add SLD to this layer

        @returns True if successful
        """

        for resource in toolkit.get_action("package_show")(None, {
            "id": self.package_id
            }).get('resources', []):
            # use first found sld file as style
            if resource.get("format", {}).lower() == "sld":
                url_ = resource.get("url", {})
                xml_file = open(helpers.file_path_from_url_shp(url_), 'r')
                xml_string = xml_file.read()
                xml_file.close()
                # validate sld according to xsd
                if (self.xml_validator(xml_string)):
                    # do some xml cleaning
                    #   lowercase all table names
                    cleaned_xml = re.sub("(<[a-zA-Z]*:PropertyName>)(\w*)(<\/[a-zA-Z]*:PropertyName>)", lambda match: match.group(1) + "" + match.group(2).lower() + "" + match.group(3), xml_string)
                    #   replace geom column name with "wkb_geometry"
                    cleaned_xml = re.sub("(<[a-zA-Z]*:?Geometry>\s*<[a-zA-Z]*:?PropertyName>)(\w*)(<\/[a-zA-Z]*:?PropertyName>\s*<\/[a-zA-Z]*:?Geometry>)",
                                         lambda match: match.group(1) + "wkb_geometry" + match.group(3), cleaned_xml)

                    # add sld to geoserver
                    self.geoserver.create_style(self.getName(), cleaned_xml, overwrite=True)
                    # connect sld to layer
                    layer = self.geoserver.get_layer(self.store.workspace.name + ":" + self.getName())

                    layer._set_default_style(self.getName())
                    self.geoserver.save(layer)

                break

    def xml_validator(self, some_xml_string, xsd_file='http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd'):
        xsd = urllib.urlopen(xsd_file)
        xsd_string = xsd.read()
        schema = etree.XMLSchema(etree.parse(StringIO(xsd_string)))
        doc = etree.parse(StringIO(some_xml_string))
        return schema.validate(doc)

    def getName(self):
        if self.resource_id.endswith("_multi"):
            return "_" + re.sub('-', '_', self.package_id)
        else:
            return "_" + re.sub('-', '_', self.name)
