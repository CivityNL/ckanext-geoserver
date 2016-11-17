from osgeo import ogr
from osgeo import osr
import zipfile
import ckanext.datastore.db as db
from os import path
from re import search
from ckanext.geoserver.misc.helpers import file_path_from_url_shp
from ckanext.geoserver.misc.helpers import folder_path_from_package_shp
from pylons import config
from ckan.plugins import toolkit
import re

import logging
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class MultiShapeFile(object):
    resource = {}
    file_path = ""
    package_id = ""
    connection_url = None
    is_valid = False
    unzipped_dir = None
    ogr_source = {
        "driver": None,
        "source": None,
        "layer": None,
        "srs": None,
        "geom_extent": None
    }
    ogr_destination = {
        "driver": None,
        "source": None,
        "layer": None,
        "srs": None,
        "geom_extent": None
    }

    def __init__(self, package_id=""):
        log.info("init.1")
        self.package_id = package_id
        # Get the resource
        self.resource = toolkit.get_action("package_show")(None, {"id": package_id})
        log.info("init.2")
        # Get the path to the file
        # url = self.resource["url"]
        # log.info(url)
        self.file_path = folder_path_from_package_shp(package_id)
        #self.file_path = fileurl
        log.info(self.file_path)
        log.info("init.3")
        self.connection_url = config.get('ckan.datastore.write_url')
        log.info("datastored.2")
        if not self.connection_url:
            log.info("datastored.3")
            raise ValueError(toolkit._("Expected datastore write url to be configured in development.ini"))
        # Check that it is a valid zip file
        # self.is_valid = self.validate()
        # log.info("init.4")

    # def validate(self):
    #     """Make sure that the uploaded zip file is a valid shapefile"""
    #     # Check that it is a zip file
    #     log.info("validate.1")
    #     log.info(self.file_path)
    #     if zipfile.is_zipfile(self.file_path):
    #         log.info("validate.1.1")
    #         # Open the zipfile as read-only
    #         with zipfile.ZipFile(self.file_path) as zf:
    #             log.info("validate.2")
    #             required = [".shp", ".shx", ".dbf"]
    #             optional = [".prj", ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih", ".ixs", ".mxs", ".atx", ".cpg", ".xml", ".fix"]
    #
    #             # Look at the file extensions in the zipfile
    #             extensions = [path.splitext(info.filename)[1] for info in zf.infolist()]
    #             log.info("validate.3")
    #             # Check that all the required extensions are there
    #             if len([ext for ext in required if ext in extensions]) == len(required):
    #                 # Check that there are not extension in there that are not required
    #                 if len([ext for ext in extensions if ext in optional]) == len(extensions) - len(required):
    #                     return True
    #     else:
    #         log.info("validate.4")
    #
    #     raise Exception(toolkit._("Not a valid shapefile"))

    # def unzip(self):
    #     """Unzip the shapefile into a pre-determined directory next to it"""
    #     # Generate the path for the directory to be unzipped to
    #     log.info("unzip.1")
    #     unzipped_dir = self.file_path[:-4] + "_UNZIPPED"
    #
    #     # Open the zipfile and extract everything (overwrite if there's stuff there??)
    #     with zipfile.ZipFile(self.file_path) as zf:
    #         log.info("unzip.2")
    #         zf.extractall(unzipped_dir)
    #     log.info("unzip.3")
    #     # Return the path to the unzipped directory
    #     return unzipped_dir

    def get_source_layer(self):
        """Get a OGRLayer for this shapefile"""
        log.info("get_source_layer.1")
        # Where is the unzipped shapefile?
        # if self.unzipped_dir is None:
            # self.unzipped_dir = self.unzip()
        log.info("get_source_layer.2")
        # Generate the OGR DataSource
        input_driver = ogr.GetDriverByName("ESRI Shapefile")
        log.info(input_driver)
        input_datasource = input_driver.Open(self.file_path, 0)
        log.info(input_datasource)
        log.info("get_source_layer.3")
        # A dataSource is always an array, but shapefiles are always by themselves. Get the layer
        layer = input_datasource.GetLayerByIndex(0)
        geom = layer.GetExtent()
        geom_extent = [[geom[2],geom[0]],[geom[3],geom[1]]]
        log.info("get_source_layer.4")
        # Cache the OGR objects so they don't get cleaned up
        self.ogr_source["driver"] = input_driver
        self.ogr_source["source"] = input_datasource
        self.ogr_source["layer"] = layer
        self.ogr_source["geom_extent"] = geom_extent

        return layer

    def ogr_source_info(self):
        source = self.ogr_source
        return source

    def get_destination_source(self):
        """Get an OGRDataSource for the default PostgreSQL destination"""
        # Generate connection details from CKAN config
        datastore_url = config.get("ckan.datastore.write_url")
        pattern = "://(?P<user>.+?):(?P<password>.+?)@(?P<host>.+?)/(?P<dbname>.+)$"
        params = search(pattern, datastore_url)
        connection = (
            params.group("host"),
            params.group("dbname"),
            params.group("user"),
            params.group("password")
        )
        ogr_connection_string = "PG: host=%s port=5432 dbname=%s user=%s password=%s" % connection

        # Generate the destination DataSource
        try:
            log.info("get_destination_source.1")
            output_driver = ogr.GetDriverByName("PostgreSQL")
            destination_source = output_driver.Open(ogr_connection_string, True)
            log.info("get_destination_source.2")

            # Cache the OGR objects so they don't get cleaned up
            self.ogr_destination["driver"] = output_driver
            self.ogr_destination["source"] = destination_source

            return destination_source
        except Exception as ex:
            log.info("get_destination_source.3")
            return None

    def create_destination_layer(self, destination_source, name, epsg=4326):
        """Create a table in the given destination OGRDataSource"""
        # Get the shapefile OGR Layer and its "definition"
        source = self.get_source_layer()
        source_def = source.GetLayerDefn()

        # Read some shapefile properties
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)

        # Cache the OGR objects so they don't get cleaned up
        self.ogr_source["srs"] = srs

        # Multi any single geometry types
        geom_type = self.output_geom(source)

        log.info("create_destination_layer.1")
        log.info(name)
        # Create the destination layer in memory
        new_layer = destination_source.CreateLayer(name, srs, geom_type, ["OVERWRITE=YES"])

        # Iterate through shapefile fields, add them to the new layer
        for i in range(source_def.GetFieldCount()):
            field_def = source_def.GetFieldDefn(i)
            new_layer.CreateField(field_def)

        # Commit it
        new_layer.CommitTransaction()

        log.info("create_destination_layer.2")
        log.info(name)

        # Cache the OGR objects so they don't get cleaned up
        self.ogr_destination["layer"] = new_layer

        return new_layer

    def get_destination_layer(self, destination_source=None, name=None):
        """Given an OGRDataSource (destination_source), find an OGRLayer within it by name"""
        if not destination_source:
            log.info("get_destination_layer.0")
            destination_source = self.get_destination_source()
            log.info(destination_source)

        if not name:
            name = self.getName()

        log.info("get_destination_layer.2.1")
        log.info(name)
        try:
            layer = destination_source.GetLayerByName(name)
        except Exception as ex:
            log.info(ex)

        log.info("get_destination_layer.3")

        if not layer:
            log.info("get_destination_layer.4")
            layer = self.create_destination_layer(destination_source, name)

        # Cache the OGR objects so they don't get cleaned up
        self.ogr_destination["layer"] = layer
        log.info("get_destination_layer.5")
        log.info(str(layer))

        return layer

    def unpublish(self):
        log.info("unpublish.0")
        log.info(self.package_id)
        conn_params = {'connection_url': self.connection_url, 'package_id': self.package_id}
        log.info("unpublish.0.1")
        engine = db._get_engine(conn_params)
        log.info("unpublish.0.2")
        connection = engine.connect()
        log.info("unpublish.1")
        sql = "DROP TABLE IF EXISTS _" + re.sub('-','_', self.package_id)
        log.info(sql)
        trans = connection.begin()
        # log.info("multiDatastored_publish.7.1")
        connection.execute(sql)
        # log.info("multiDatastored_publish.7.2")
        trans.commit()
        # log.info("multiDatastored_publish.7.3")
        #
        connection.close()

        return True

    def publish(self, destination_layer=None):
        """Move shapefile data into the given destination OGRLayer"""
        if not destination_layer:
            destination_layer = self.get_destination_layer()

        log.info("publish.1")

        # Get information about the destination layer
        dest_def = destination_layer.GetLayerDefn()
        target_srs = destination_layer.GetSpatialRef()
        log.info("publish.2")

        # Cache the OGR objects so they don't get cleaned up
        self.ogr_destination["srs"] = target_srs

        log.info("publish.3")
        # Setup the coordinate transformation
        source = self.get_source_layer()
        source_srs = source.GetSpatialRef()
        transformation = osr.CoordinateTransformation(source_srs, target_srs)

        log.info("publish.4")
        # Remove any features currently in the destination layer -- they'll be replaced by shapefile contents
        dest_record = destination_layer.GetNextFeature()
        while dest_record is not None:
            destination_layer.DeleteFeature(dest_record.GetFID())
            dest_record = destination_layer.GetNextFeature()

        log.info("publish.5")
        # Iterate through the shapefile features. Project each one and add it to the destination
        source_record = source.GetNextFeature()
        log.info("publish.6")

        while source_record is not None:
            # log.info("publish.6.1")
            # Create a new, blank feature in the destination layer
            dest_record = ogr.Feature(dest_def)
            # log.info("publish.6.2")
            # Set its geometry
            geom = source_record.GetGeometryRef()
            # log.info("publish.6.3")
            # Transform
            geom.Transform(transformation)
            # log.info("publish.6.4")
            # Force multi onto geoms
            geom_type = geom.GetGeometryType()
            force_function = self.output_geom_force(geom_type)
            geom = force_function(geom)
            # log.info("publish.6.5")
            # Set its attributes from the source feature
            dest_record.SetFrom(source_record)
            dest_record.SetGeometry(geom)
            # log.info("publish.6.6")
            # Save it to the destination layer and iterate
            destination_layer.CreateFeature(dest_record)
            source_record = source.GetNextFeature()
            # log.info("publish.6.7")

        log.info("publish.7")
        return True

    def reproject(self, feature, target_srs):
        """Reproject a single feature's geometry into a new SRS and return the new geometry"""
        # Get the appropriate transformations and build a reprojected geometry
        source_srs = self.ogr_source["layer"].GetSpatialRef()
        transformation = osr.CoordinateTransformation(source_srs, target_srs)

        # Cache the OGR objects so they don't get cleaned up
        self.ogr_source["srs"] = source_srs
        self.transformation = transformation

        return feature.GetGeometryRef().Transform(transformation)

    def get_name(self):
        log.info("get_name.1")
        if self.unzipped_dir is None:
            self.unzipped_dir = self.unzip()

        # Generate the OGR DataSource
        inputDriver = ogr.GetDriverByName("ESRI Shapefile")
        dataSource = inputDriver.Open(self.unzipped_dir, 0)
        log.info("get_name.2")
        # A dataSource is always an array, but shapefiles are always by themselves. Get the layer
        return dataSource.GetLayerByIndex(0).GetName()

    def table_name(self):
        return self.get_name().lower().replace("-", "_").replace(".", "_") # Postgresql will have the name screwballed

    def getName(self):
        log.info("getName.1")
        id = self.resource['id']
        log.info("getName.2")
        id = re.sub('-','_', id)
        log.info("getName.3")
        name = '_'+id
        log.info("getName.4")
        return name.encode('ascii', 'ignore')

    def output_geom(self, source):
        # Find the geometry type of the source shapefile
        source_def = source.GetLayerDefn()
        geom_type = source_def.GetGeomType()

        # Convert to Multi
        geom_type = ogr.wkbMultiLineString if geom_type == ogr.wkbLineString else geom_type
        geom_type = ogr.wkbMultiPolygon if geom_type == ogr.wkbPolygon else geom_type
        geom_type = ogr.wkbMultiPoint if geom_type == ogr.wkbPoint else geom_type

        return geom_type

    def output_geom_force(self, geom_type):
        # Return the correct function
        if geom_type == ogr.wkbLineString:
            return ogr.ForceToMultiLineString
        elif geom_type == ogr.wkbPolygon:
            return ogr.ForceToMultiPolygon
        elif geom_type == ogr.wkbPoint:
            return ogr.ForceToMultiPoint
        else:
            def do_nothing(geom):
                return geom
            return do_nothing
