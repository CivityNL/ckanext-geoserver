# coding=utf-8
from pylons import config
import ckanext.datastore.db as db
from ckan.plugins import toolkit
from sqlalchemy.exc import ProgrammingError

import re
import json


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
    descriptor_name = None

    def __init__(self, package_id, lat_field, lng_field, join_key):
        self.package_id = package_id
        self.lat_col = lat_field
        self.lng_col = lng_field
        self.join_key = join_key
        self.connection_url = config.get('ckan.datastore.write_url')
        self.descriptor_name = config.get('geoserver.descriptor_name', 'schema_descriptor')
        if not self.connection_url:
            raise ValueError(toolkit._("Expected datastore write url to be configured in development.ini"))

    def clean_fields(self, connection, field_list):
        """
        CSV files can have spaces in column names, which will carry over into PostGIS tables.  Geoserver can not handle
        spaces in field names because they will generate namespace errors in XML, which renders the OGC service as
        invalid.  This function looks for column names with spaces and replaces those spaces with underscores.
        """
        for item in field_list:
            dirty = item['id']
            clean = self.clean_name(dirty, '_')

            if dirty != clean:
                sql = 'ALTER TABLE "{res_id}" RENAME COLUMN "{old_val}" TO "{new_val}"'.format(
                    res_id=self.resource_id,
                    old_val=item['id'],
                    new_val=clean
                    # new_val=dirty.replace(" ","_")
                    )
                trans = connection.begin()
                connection.execute(sql)
                trans.commit()
            else:
                pass

    def dirty_fields(self, connection, field_list):
        for item in field_list:
            dirty = item['id']
            clean = self.clean_name(dirty, ' ')

            if dirty != clean:
                sql = 'ALTER TABLE "{res_id}" RENAME COLUMN "{old_val}" TO "{new_val}"'.format(
                    res_id=self.resource_id,
                    old_val=item['id'],
                    new_val=clean
                    # new_val=dirty.replace("_"," ")
                    )
                trans = connection.begin()
                connection.execute(sql)
                trans.commit()
            else:
                pass

    def unpublish(self):
        conn_params = {
            'connection_url': self.connection_url,
            'package_id': self.package_id
        }
        engine = db._get_engine(conn_params)
        connection = engine.connect()
        sql = "DROP MATERIALIZED VIEW IF EXISTS " + self.getName()
        trans = connection.begin()
        connection.execute(sql)
        trans.commit()
        connection.close()
        return True

    def publish(self):
        """
        Checks and generates the 'Geometry' column in the table for Geoserver to work on.
        Resource in datastore database is checked for Geometry field. If the field doesn't exists then calculates the
        geometry field value and creates it in the table.
        """
        pkg = toolkit.get_action('package_show')(None, {
            'id': self.package_id
        })
        extras = pkg.get('extras', [])

        for extra in extras:
            key = extra.get('key', None)
            if key == self.descriptor_name:
                schema_descriptor = json.loads(extra.get('value'))
                break

        obs = []
        geom = []

        for member in schema_descriptor.get("members"):
            if member.get('resource_type') == 'observed_geometries':
                geom_fields = member.get('fields')
                for ids in member.get('resource_name'):
                    geom.append(ids)
            if member.get('resource_type') == 'observations':
                obs_fields = member.get('fields')
                for ids in member.get('resource_name'):
                    obs.append(ids)

        if self.join_key is None:
            for geom_field in geom_fields:
                for obs_field in obs_fields:
                    if geom_field.get('field_id').lower() == obs_field.get('field_id').lower():
                        self.join_key = geom_field.get('field_id').lower()

        if len(geom) != 1 and len(obs) == 0:
            raise toolkit.ObjectNotFound(toolkit._("Mutliple geometry files found"))

        # Get the connection parameters for the datastore
        conn_params = {
            'connection_url': self.connection_url,
            'resource_id': geom[0]
        }
        engine = db._get_engine(conn_params)
        connection = engine.connect()
        try:
            # This will fail with a ProgrammingError if the table does not exist
            fields = db._get_fields({
                                        "connection": connection
                                    }, conn_params)
        except ProgrammingError as ex:
            raise toolkit.ObjectNotFound(toolkit._("Resource not found in datastore database"))

        # If there is not already a geometry column...
        if not True in set(col['id'] == self.geo_col for col in fields):
            # ... append one
            fields.append({
                              'id': self.geo_col,
                              'type': u'geometry'
                          })

            self.clean_fields(connection, fields)
            # SQL to create the geometry column
            sql = "SELECT AddGeometryColumn('public', '%s', '%s', 4326, 'GEOMETRY', 2)" % (geom[0], self.geo_col)
            # Create the new column
            trans = connection.begin()
            connection.execute(sql)
            trans.commit()

            # Update values in the Geometry column
            sql = "UPDATE \"%s\" SET \"%s\" = st_geometryfromtext('POINT(' || \"%s\" || ' ' || \"%s\" || ')', 4326)"
            sql = sql % (geom[0], self.geo_col, self.lng_col, self.lat_col)

            trans = connection.begin()
            connection.execute(sql)
            trans.commit()

        selectsql = "SELECT "

        for fields in geom_fields:
            if fields.get('field_type').lower() == 'date':
                if fields.get('date_format') is not None:
                    postgresdate = self.convertIsoToPostgres(fields.get('date_format'))
                else:
                    postgresdate = self.convertIsoToPostgres('default')
                selectsql += "to_timestamp(CAST(\"" + geom[0] + "\".\"" + self.clean_name(fields.get('field_id'), '_') + "\" as text), \'" + postgresdate + "\') as \"geometry." + self.clean_name(
                    fields.get('field_id'), '_') + "\", "
            else:
                selectsql += "\"" + geom[0] + "\".\"" + self.clean_name(fields.get('field_id'), '_') + "\" as \"geometry." + self.clean_name(fields.get('field_id'), '_') + "\", "
                if fields.get('field_id').lower() == self.join_key:
                    geom_key = fields.get('field_id')

        selectsql += "\"" + geom[0] + "\".\"" + self.geo_col + "\" as \"geometry." + self.geo_col + "\", "

        for fields in obs_fields:
            if fields.get('field_type').lower() == 'date':
                if fields.get('date_format') is not None:
                    postgresdate = self.convertIsoToPostgres(fields.get('date_format'))
                else:
                    postgresdate = self.convertIsoToPostgres('default')
                selectsql += "to_timestamp(CAST(observations.\"" + self.clean_name(fields.get('field_id'), '_') + "\" as text), \'" + postgresdate + "\') as \"geometry." + self.clean_name(
                    fields.get('field_id'), '_') + "\", "
            else:
                selectsql += "observations.\"" + self.clean_name(fields.get('field_id'), '_') + "\" as \"observations." + self.clean_name(fields.get('field_id'), '_') + "\", "
                if fields.get('field_id').lower() == self.join_key:
                    obs_key = fields.get('field_id')

        selectsql = selectsql[:-2] + " "
        selectsql += "FROM "
        selectsql += "public.\"" + geom[0] + "\" "

        selectsql += "INNER JOIN ("

        for entry in obs:
            selectsql += "SELECT * FROM public.\"" + entry + "\" UNION ALL "

        selectsql = selectsql[:-11] + ") as observations "
        selectsql += "ON public.\"" + geom[0] + "\".\"" + geom_key + "\" = observations.\"" + obs_key + "\""

        sql = "DROP MATERIALIZED VIEW IF EXISTS \"%s\"; CREATE MATERIALIZED VIEW \"%s\" AS " + selectsql
        # sql = "DROP VIEW IF EXISTS \"_%s\"; CREATE VIEW \"_%s\" AS " + selectsql
        sql = sql % (self.getName(), self.getName())
        trans = connection.begin()
        connection.execute(sql)
        trans.commit()

        connection.close()
        return True

    def convertIsoToPostgres(self, date):
        if date == 'default':
            return self.convertIsoToPostgres('YYYY-MM-ddTHH:mm:ssZ')
        postgres = date
        postgres = postgres.replace('T', '"T"')
        postgres = postgres.replace('Z', '"Z"')
        postgres = postgres.replace('mm', 'MI')
        postgres = postgres.replace('dd', 'DD')
        postgres = postgres.replace('hh', 'HH12')
        postgres = postgres.replace('HH', 'HH24')
        postgres = postgres.replace('SSS', 'MS')
        postgres = postgres.replace('ss', 'SS')
        return postgres

    def clean_name(self, name, form):
        clean = re.sub('µ', 'micro_', name)
        clean = re.sub('/', '_per_', clean)
        clean = re.sub('[][}{()?$%&!#*^°@,;: ]', form, clean)
        if re.match('^[0-9]', clean):
            clean = "_" + clean
        return clean

    def table_name(self):
        return self.resource_id

    def getName(self):
        return "_" + re.sub('-', '_', self.package_id)
