# coding=utf-8
from pylons import config
import ckanext.datastore.db as db
from ckan.plugins import toolkit
from sqlalchemy.exc import ProgrammingError
import logging
import re
import json
log = logging.getLogger(__name__)

class MultiDatastored(object):
    """
    Handles the resources which are loaded by Datastore extension. Makes the details available for Geoserver to access.
    """

    package_id = None
    lat_col = None
    lng_col = None
    join_key = None
    geo_col = 'Shape'
    connection_url = None

    def __init__(self, package_id, lat_field, lng_field, join_key):
        log.info("multiDatastored.1")
        self.package_id = package_id
        self.lat_col = lat_field
        self.lng_col = lng_field
        self.join_key = join_key
        self.connection_url = config.get('ckan.datastore.write_url')
        log.info("multiDatastored.2")
        if not self.connection_url:
            log.info("multiDatastored.3")
            raise ValueError(toolkit._("Expected datastore write url to be configured in development.ini"))

    def clean_fields(self, connection, field_list):
        """
        CSV files can have spaces in column names, which will carry over into PostGIS tables.  Geoserver can not handle
        spaces in field names because they will generate namespace errors in XML, which renders the OGC service as
        invalid.  This function looks for column names with spaces and replaces those spaces with underscores.
        """
        for item in field_list:
            dirty = item['id']
            #clean = dirty.replace(" ","_")
            clean = re.sub('µ','micro_', dirty)
            clean = re.sub('/','_per_', clean)
            clean = re.sub('[][}{()?$%&!#*^°@,;: ]', '_', clean)
            if re.match('^[0-9]', clean):
                clean = "_"+clean

            log.info("multiDatastored_clean_fields.1")
            if dirty != clean:
                sql = 'ALTER TABLE "{res_id}" RENAME COLUMN "{old_val}" TO "{new_val}"'.format(
                    res_id=self.resource_id,
                    old_val=item['id'],
                    new_val=clean
                    #new_val=dirty.replace(" ","_")
                )
                log.info("multiDatastored_clean_fields.2")
                trans = connection.begin()
                log.info("multiDatastored_clean_fields.3")
                connection.execute(sql)
                log.info("multiDatastored_clean_fields.4")
                trans.commit()
                log.info("multiDatastored_clean_fields.5")
            else:
                log.info("multiDatastored_clean_fields.6")
                pass

    def dirty_fields(self, connection, field_list):
        for item in field_list:
            dirty = item['id']
            #clean = dirty.replace(" ","_")
            clean = re.sub('µ','micro_', dirty)
            clean = re.sub('/','_per_', clean)
            clean = re.sub('[][}{()?$%&!#*^°@,;: ]', ' ', clean)
            if re.match('^[0-9]', clean):
                clean = "_"+clean

            if dirty != clean:
                sql = 'ALTER TABLE "{res_id}" RENAME COLUMN "{old_val}" TO "{new_val}"'.format(
                    res_id=self.resource_id,
                    old_val=item['id'],
                    new_val=clean
                    #new_val=dirty.replace("_"," ")
                )
                trans = connection.begin()
                connection.execute(sql)
                trans.commit()
            else:
                pass


    def publish(self):
        """
        Checks and generates the 'Geometry' column in the table for Geoserver to work on.
        Resource in datastore database is checked for Geometry field. If the field doesn't exists then calculates the
        geometry field value and creates it in the table.
        """
        log.info("multiDatastored_publish.1")
        # Get resource_id of observed geometries table

        pkg = toolkit.get_action('package_show')(None, {'id': self.package_id})
        log.info("multiDatastored_publish.1.0")
        extras = pkg.get('extras', [])
        log.info("multiDatastored_publish.1.1")

        for extra in extras:
            log.info("multiDatastored_publish.1.1")
            key = extra.get('key', None)
            log.info("multiDatastored_publish.1.2")
            if key == 'resource_descriptor':
                log.info("multiDatastored_publish.1.3")
                resource_descriptor = json.loads(extra.get('value'))
                log.info("multiDatastored_publish.1.4")
                break


        obs = []
        geom = []

        log.info(resource_descriptor)

        log.info("multiDatastored_publish.1.4.0")
        log.info(resource_descriptor.get("members"))
        for member in resource_descriptor.get("members"):
            log.info("multiDatastored_publish.1.4.1")
            if member.get('resource_type') == 'observed_geometries':
                geom_fields = member.get('fields')
                log.info("multiDatastored_publish.1.4.2")
                for ids in member.get('resource_name'):
                    log.info("multiDatastored_publish.1.4.3")
                    geom.append(ids)
            if member.get('resource_type') == 'observations':
                log.info("multiDatastored_publish.1.4.4")
                obs_fields = member.get('fields')
                for ids in member.get('resource_name'):
                    log.info("multiDatastored_publish.1.4.5")
                    obs.append(ids)

        log.info("multiDatastored_publish.1.5")
        log.info(obs)
        log.info(geom)

        if len(geom) != 1 and len(obs) == 0:
            raise toolkit.ObjectNotFound(toolkit._("Mutliple geometry files found"))

        # Get the connection parameters for the datastore
        conn_params = {'connection_url': self.connection_url, 'resource_id': geom[0]}
        engine = db._get_engine(conn_params)
        connection = engine.connect()
        log.info("multiDatastored_publish.2")
        try:
            log.info("multiDatastored_publish.2.1")
            # This will fail with a ProgrammingError if the table does not exist
            fields = db._get_fields({"connection": connection}, conn_params)
        except ProgrammingError as ex:
            log.info("multiDatastored_publish.3")
            raise toolkit.ObjectNotFound(toolkit._("Resource not found in datastore database"))

        # If there is not already a geometry column...
        if not True in set( col['id'] == self.geo_col for col in fields ):
            # ... append one
            log.info("multiDatastored_publish.4")
            fields.append({'id': self.geo_col, 'type': u'geometry'})

            self.clean_fields(connection, fields)
            log.info("multiDatastored_publish.4.1")
            # SQL to create the geometry column
            sql = "SELECT AddGeometryColumn('public', '%s', '%s', 4326, 'GEOMETRY', 2)" % (geom[0], self.geo_col)
            log.info(sql)
            # Create the new column
            trans = connection.begin()
            log.info("multiDatastored_publish.4.2")
            log.info(sql)
            connection.execute(sql)
            log.info("multiDatastored_publish.4.3")
            trans.commit()
            log.info("multiDatastored_publish.5")

            # Update values in the Geometry column
            sql = "UPDATE \"%s\" SET \"%s\" = st_geometryfromtext('POINT(' || \"%s\" || ' ' || \"%s\" || ')', 4326)"
            sql = sql % (geom[0], self.geo_col, self.lng_col, self.lat_col)

            log.info(sql)
            log.info("multiDatastored_publish.5.1")
            trans = connection.begin()
            log.info("multiDatastored_publish.5.2")
            log.info(sql)
            connection.execute(sql)
            log.info("multiDatastored_publish.5.3")
            trans.commit()
            log.info("multiDatastored_publish.6")
            #return True

        log.info("multiDatastored_publish.6.1")
        selectsql = "SELECT "

        for fields in geom_fields:
            selectsql += "\""+geom[0]+"\".\""+fields.get('field_id')+"\" as \"geometry."+fields.get('field_id')+"\", "
            if fields.get('field_id').lower() == 'stations_id':
                geom_key = fields.get('field_id')

        log.info("multiDatastored_publish.6.2")
        selectsql += "\""+geom[0]+"\".\""+self.geo_col+"\" as \"geometry."+self.geo_col+"\", "
        log.info("multiDatastored_publish.6.2.1")

        for fields in obs_fields:
            selectsql += "observations.\"" + fields.get('field_id') + "\" as \"observations."+fields.get('field_id')+"\", "
            if fields.get('field_id').lower() == 'stations_id':
                obs_key = fields.get('field_id')

        selectsql = selectsql[:-2] + " "
        selectsql += "FROM "
        selectsql += "public.\""+geom[0]+"\" "

        selectsql += "INNER JOIN ("

        log.info("multiDatastored_publish.6.3")
        for entry in obs:
            selectsql += "SELECT * FROM public.\""+entry+"\" UNION ALL "

        log.info("multiDatastored_publish.6.4")
        selectsql = selectsql[:-11] + ") as observations "
        selectsql += "ON public.\""+geom[0]+"\".\""+geom_key+"\" = observations.\""+obs_key+"\""

        log.info("multiDatastored_publish.7")
        sql = "DROP MATERIALIZED VIEW IF EXISTS \"_%s\"; CREATE MATERIALIZED VIEW \"_%s\" AS " + selectsql
        # sql = "DROP VIEW IF EXISTS \"_%s\"; CREATE VIEW \"_%s\" AS " + selectsql
        sql = sql % (re.sub('-','_', self.package_id), re.sub('-','_', self.package_id))
        log.info(sql)
        trans = connection.begin()
        log.info("multiDatastored_publish.7.1")
        connection.execute(sql)
        log.info("multiDatastored_publish.7.2")
        trans.commit()
        log.info("multiDatastored_publish.7.3")

        connection.close()
        return True

    def table_name(self):
        return self.resource_id
