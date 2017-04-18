# coding=utf-8
import requests
from os import path
import re
from ckan.plugins import toolkit
from pylons import config
import logging
import json
import os

import shutil
import urllib2
from os import makedirs
from contextlib import closing
from zipfile import ZipFile, ZIP_DEFLATED
import ckanext.geoserver.misc.helpers as helpers

log = logging.getLogger(__name__)


class MultiRasterFile(object):
    """
    Handles the resources which are loaded by Datastore extension. Makes the details available for Geoserver to access.
    """

    package_id = None
    connection_url = None
    zipFileLocation = None
    descriptor_name = None

    def __init__(self, package_id):
        self.package_id = package_id
        self.connection_url = config.get('ckan.datastore.write_url')
        self.zipFileLocation = config.get('ckan.storage.directory', '/var/tmp/')
        self.descriptor_name = config.get('geoserver.descriptor_name', 'schema_descriptor')
        if not self.connection_url:
            raise ValueError(toolkit._("Expected datastore write url to be configured in development.ini"))

    def unpublish(self):
        # TODO: service to delete file in geoserver file system?
        return True

    def publish(self):
        """
        Checks and generates the 'Geometry' column in the table for Geoserver to work on.
        Resource in datastore database is checked for Geometry field. If the field doesn't exists then calculates the
        geometry field value and creates it in the table.
        """

        self.zipFileLocation = self.zipFileLocation + "GeoserverUpload/" + self.package_id + "/zipped/"

        if not path.exists(self.zipFileLocation):
            makedirs(self.zipFileLocation)

        extras = toolkit.get_action("package_show")(None, {
            "id": self.package_id
        }).get("extras", [])

        for extra in extras:
            key = extra.get('key', None)
            if key == self.descriptor_name:
                schema_descriptor = json.loads(extra.get('value'))
                break

        for member in schema_descriptor.get("members"):
            name_regex = member.get("name_regex").decode('string_escape')
            resource_name = member.get("resource_name")
            break

        m = re.search('<timeregex>(.+?)\)\\\\\.tif', name_regex)
        if m:
            timeregex = m.group(1)

        # clear tmp folder
        for the_file in os.listdir(self.zipFileLocation):
            file_path = os.path.join(self.zipFileLocation, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)

        # copy all geotiffs from schema descriptor into tmp folder
        for resource in resource_name:
            url_ = toolkit.get_action("resource_show")(None, {
                "id": resource
            }).get("url", {})
            label = url_.rsplit('/', 1)[-1]
            tmpFile = urllib2.urlopen(url_)
            with open(self.zipFileLocation + label, 'wb') as fp:
                shutil.copyfileobj(tmpFile, fp)

        # create indexer.properties file
        with open(self.zipFileLocation + "/indexer.properties", "w+") as f:
            f.write("TimeAttribute=time\n")
            f.write("Schema=*the_geom:Polygon,location:String,time:java.util.Date\n")
            f.write("PropertyCollectors=TimestampFileNameExtractorSPI[timeregex](time)\n")

        # create timeregex.properties file based on regex
        with open(self.zipFileLocation + "/timeregex.properties", "w+") as f:
            f.write("regex=" + timeregex+"\n")

        # create zip archive
        with closing(ZipFile(self.zipFileLocation + "/" + self.package_id + ".zip", "w", ZIP_DEFLATED)) as z:
            for root, dirs, files in os.walk(self.zipFileLocation):
                # NOTE: ignore empty directories
                for fn in files:
                    if not fn.endswith(".zip"):
                        absfn = os.path.join(root, fn)
                        if self.zipFileLocation.endswith(os.sep):
                            zfn = absfn[len(self.zipFileLocation):]
                        else:
                            zfn = absfn[len(self.zipFileLocation) + len(os.sep):]
                        z.write(absfn, zfn)

        # save zipFile Location
        self.zipFileLocation = self.zipFileLocation + "" + self.package_id + ".zip"

        return True

    def getName(self):
        log.info("getName.1")
        return "_" + re.sub('-', '_', self.package_id)
