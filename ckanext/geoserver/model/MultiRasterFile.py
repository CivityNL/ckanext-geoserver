# coding=utf-8
import requests
from os import path
import re
from ckan.plugins import toolkit
from pylons import config
import logging
import shutil
import urllib2
from os import makedirs
import ckanext.geoserver.misc.helpers as helpers

log = logging.getLogger(__name__)


class MultiRasterFile(object):
    """
    Handles the resources which are loaded by Datastore extension. Makes the details available for Geoserver to access.
    """

    package_id = None
    connection_url = None
    
    def __init__(self, package_id):
        log.info("multiRasterfile.1")
        self.package_id = package_id
        self.connection_url = config.get('ckan.datastore.write_url')
        log.info("multiRasterfile.2")
        if not self.connection_url:
            log.info("multiRasterfile.3")
            raise ValueError(toolkit._("Expected datastore write url to be configured in development.ini"))

    def unpublish(self):
        #TODO: service to delete file in geoserver file system?
        return True

    def publish(self):
        """
        Checks and generates the 'Geometry' column in the table for Geoserver to work on.
        Resource in datastore database is checked for Geometry field. If the field doesn't exists then calculates the
        geometry field value and creates it in the table.
        """
        log.info("multiRasterfile_publish.1")
        testserver = "http://10.211.55.11:8080/GeoserverService/upload/file"

        valid_endings = ["geotiff"]
        for resource in toolkit.get_action("package_show")(None, {"id": self.package_id}).get('resources', []):
            for valid in valid_endings:
                if resource.get("format", {}) == valid:
                    url = resource.get("url", {})
                    break

        tmpFolder = "/var/tmp/" + self.package_id + "/"

        if not path.exists(tmpFolder):
            makedirs(tmpFolder)

        label = url.rsplit('/', 1)[-1]
        log.info(label)
        tmpFile = urllib2.urlopen(url)
        log.info(tmpFolder)
        log.info(tmpFile)
        with open(tmpFolder + label, 'wb') as fp:
            shutil.copyfileobj(tmpFile, fp)

        testfile = tmpFolder + label

        files = {'file': (testfile, open(testfile, "rb"), 'image/tiff', {"Expires": "0"}), 'foldername':self.package_id}
        r = requests.post(testserver, files=files)
        return True

    def getName(self):
        log.info("getName.1")
        return "_" + re.sub('-', '_', self.package_id)
