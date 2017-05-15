import logging
import ckan.logic as logic
import ckanext.geoserver.misc.helpers as helpers
from ckanext.geoserver.model.Geoserver import Geoserver
from ckanext.geoserver.model.Layer import Layer
from ckanext.geoserver.model.ProcessOGC import HandleWMS
from ckan.plugins import toolkit
from pylons.i18n import _
from pylons import config
import ckan.lib.helpers as h
import socket
import json

log = logging.getLogger(__name__)
_get_or_bust = logic.get_or_bust


def publish_ogc(context, data_dict):
    """
    Publishes the resource details as a Geoserver layer based on the input details.
    If the layer creation is successful then returns "Success" msg, otherwise raises an Exception.
    """

    # check if the user is allowed to edit/publish this package
    check_data_dict = {
        'id': data_dict.get("package_id", None)
    }
    logic.check_access('package_update', context, check_data_dict)

    # Gather inputs
    resource_id = data_dict.get("resource_id", None)
    layer_name = data_dict.get("layer_name", resource_id)
    username = context.get("user", None)
    package_id = data_dict.get("package_id", None)
    join_key = data_dict.get("join_key", None)
    lat_field = data_dict.get("col_latitude", None)
    lng_field = data_dict.get("col_longitude", None)
    datastore = data_dict.get("geoserver_datastore", None)
    layer_version = data_dict.get("layer_version", "1.0")
    workspace_name = data_dict.get("workspace_name", None)
    api_call_type = context.get("api_call_type", "ui")

    descriptor_name = config.get('geoserver.descriptor_name', 'schema_descriptor')

    # check if API call only contains id (can contain package_id, join_key)
    ismulti = False
    if data_dict.get("package_id", None) is not None and len(data_dict) <= 2:
        pkg = toolkit.get_action('package_show')(None, {
            'id': package_id
            })
        extras = pkg.get('extras', [])

        for extra in extras:
            key = extra.get('key', None)
            if key == descriptor_name:
                schema_descriptor = json.loads(extra.get('value'))

        # have schema descriptor
        if schema_descriptor:
            # MultiShapefile
            if helpers.shapefile_publishing_requirements_fulfiled(data_dict.get("package_id", None)):
                resource_id = "shapefile_multi"
                layer_name = "shapefile_multi"
                workspace_name = "shapefile_multi"
            else:
                # MultiRasterfile
                if helpers.geoserver_rasters_to_publish(data_dict.get("package_id", None)):
                    resource_id = "schema_descriptor_timeseries_multi"
                    layer_name = "schema_descriptor_timeseries_multi"
                    workspace_name = "schema_descriptor_timeseries_multi"
                else:
                    # MultiDatastore
                    for member in schema_descriptor.get("members"):
                        # if single
                        if member.get('resource_type') == 'observations_with_geometry':
                            resource_id = member.get('resource_name')[0]
                            layer_name = member.get('resource_name')[0]
                            workspace_name = member.get('resource_name')[0]
                            for field in member.get('fields'):
                                if field.get('field_role') == "latitude":
                                    lat_field = field.get('field_id')
                                if field.get('field_role') == "longitude":
                                    lng_field = field.get('field_id')
                        # if multi get lat/lng from correct file
                        if member.get('resource_type') == 'observed_geometries':
                            ismulti = True
                            resource_id = "schema_descriptor_multi"
                            layer_name = "schema_descriptor_multi"
                            workspace_name = "schema_descriptor_multi"
                            for field in member.get('fields'):
                                if field.get('field_role') == "latitude":
                                    lat_field = field.get('field_id')
                                if field.get('field_role') == "longitude":
                                    lng_field = field.get('field_id')
                            if join_key is None:
                                # collect all fields of geom
                                geom_fields = member.get('fields')
                        if member.get('resource_type') == 'observations':
                            if join_key is None:
                                # collect all fields of observations
                                obs_fields = member.get('fields')

                    if join_key is None and ismulti:
                        # compare fields and select best for
                        for geom_field in geom_fields:
                            for obs_field in obs_fields:
                                if geom_field.get('field_id').lower() == obs_field.get('field_id').lower():
                                    join_key = geom_field.get('field_id').lower()
                                    # no schema_descriptor
                                    # not supported yet
                                    # else:

    # Check that you have everything you need
    if None in [resource_id, layer_name, username, package_id, layer_version, workspace_name]:
        raise Exception(toolkit._("Not enough information to publish resource"))

    # Publish a layer
    def pub():
        layer = Layer.publish(package_id, resource_id, workspace_name, layer_name, layer_version, username, datastore, lat_field=lat_field, lng_field=lng_field, join_key=join_key)
        return layer

    try:
        l = pub()
        if l is None:
            log.debug("Failed to generate a Geoserver layer.")
            if api_call_type == 'ui':
                h.flash_error(_("Failed to generate a Geoserver layer."))
            raise Exception(toolkit._("Layer generation failed"))
        else:
            if data_dict.get("package_id", None) is not None and len(data_dict) <= 2:
                helpers.update_package_published_status(data_dict.get("package_id", None), True)
            # csv content should be spatialized or a shapefile uploaded, Geoserver updated, resources appended.
            #  l should be a Layer instance. Return whatever you wish to
            log.debug("This resource has successfully been published as an OGC service.")
            if api_call_type == 'ui':
                h.flash_success(_("This resource has successfully been published as an OGC service."))
            return {
                "success": True,
                "message": _("This resource has successfully been published as an OGC service.")
            }
    except socket.error:
        log.debug("Error connecting to Geoserver.")
        if api_call_type == 'ui':
            h.flash_error(_("Error connecting to Geoserver."))


def unpublish_ogc(context, data_dict):
    """
    Un-publishes the Geoserver layer based on the resource identifier. Retrieves the Geoserver layer name and package
     identifier to construct layer and remove it.
    """

    # check if the user is allowed to edit/publish this package
    check_data_dict = {
        'id': data_dict.get("package_id", None)
    }
    logic.check_access('package_update', context, check_data_dict)

    resource_id = data_dict.get("resource_id", None)
    layer_name = data_dict.get("layer_name", None)
    username = context.get('user')
    api_call_type = data_dict.get("api_call_type", "ui")
    package_id = data_dict.get("package_id", None)

    descriptor_name = config.get('geoserver.descriptor_name', 'schema_descriptor')

    pkg = toolkit.get_action('package_show')(None, {
        'id': package_id
        })
    extras = pkg.get('extras', [])

    for extra in extras:
        key = extra.get('key', None)
        if key == descriptor_name:
            schema_descriptor = json.loads(extra.get('value'))

    # if api call
    if data_dict.get("package_id", None) is not None and len(data_dict) == 1:
        if schema_descriptor:
            # MultiShapefile
            if helpers.shapefile_publishing_requirements_fulfiled(data_dict.get("package_id", None)):
                resource_id = "shapefile_multi"
                layer_name = "shapefile_multi"
            # MultiRasterfile
            elif helpers.geoserver_rasters_to_publish(data_dict.get("package_id", None)):
                    resource_id = "schema_descriptor_timeseries_multi"
                    layer_name = "schema_descriptor_timeseries_multi"
            # MultiDatastore
            else:
                for member in schema_descriptor.get("members"):
                    # if single
                    if member.get('resource_type') == 'observations_with_geometry':
                        resource_id = member.get('resource_name')[0]
                        layer_name = member.get('resource_name')[0]
                    # if multi get lat/lng from correct file
                    if member.get('resource_type') == 'observed_geometries':
                        resource_id = "schema_descriptor_multi"
                        layer_name = "schema_descriptor_multi"

    # if resource_id.endswith("_multi"):
    #     file_resource = toolkit.get_action("package_show")(None, {
    #         "id": package_id
    #     })
    # else:
    #     file_resource = toolkit.get_action("resource_show")(None, {
    #         "id": resource_id
    #     })

    geoserver = Geoserver.from_ckan_config()

    def unpub():
        layer = Layer.unpublish(geoserver, layer_name, resource_id, package_id, username)
        return layer

    try:
        layer = unpub()
    except socket.error:
        log.debug("Error connecting to geoserver. Please contact the site administrator if this problem persists.")
        if api_call_type == 'ui':
            h.flash_error(_("Error connecting to geoserver. Please contact the site administrator if this problem persists."))
        return False

    if data_dict.get("package_id", None) is not None and len(data_dict) <= 2:
        helpers.update_package_published_status(data_dict.get("package_id", None), False)

    log.debug("This resource has successfully been unpublished.")
    if api_call_type == 'ui':
        h.flash_success(_("This resource has successfully been unpublished."))
    return {
        "success": True,
        "message": _("This resource has successfully been unpublished.")
    }


def map_search_wms(context, data_dict):
    def wms_resource(resource):
        if resource.get("protocol", {}) == "WMS":
            return True
        else:
            return False

    def get_wms_data(resource):
        resourceURL = resource.get("url", {})
        this_wms = HandleWMS(resourceURL)
        return this_wms.get_layer_info(resource)

    try:
        pkg_id = data_dict.get("pkg_id")
        pkg = toolkit.get_action("package_show")(None, {
            'id': pkg_id
        })
        resources = filter(wms_resource, pkg.get('resources'))

        this_data = map(get_wms_data, resources)

        return this_data
    except:
        return [{
                    'ERROR': 'SERVER_ERROR'
                }]


def update_package_published_status(context, data_dict):
    # check if the user is allowed to edit/publish this package
    check_data_dict = {
        'id': data_dict.get("package_id", None)
    }
    logic.check_access('package_update', context, check_data_dict)

    package_id = data_dict.get("package_id", None)
    if data_dict.get("status", None).lower() == "true":
        status = True
    else:
        status = False

    if helpers.update_package_published_status(package_id, status):
        return {
            "success": True,
            "message": _("The published-status of this package has successfully been changed.")
        }
    else:
        return {
            "error": True,
            "message": _("While changing the published-status of this package an error occurred.")
        }
