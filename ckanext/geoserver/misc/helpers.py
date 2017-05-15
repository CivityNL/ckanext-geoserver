import re
import urllib2
from ckan import model
from ckan.plugins import toolkit
from ckan.logic import NotFound
from ckan.controllers import storage
from pylons import config
from os import path
from os import makedirs
import shutil

def check_published(resource):
    """
    Checks whether given resource is already spatialized. If spatialized returns True otherwise False.
    """
    spatialized = False
    resource_id = resource['id']
    package_id = model.Resource.get(resource_id).resource_group.package_id
    package = model.Package.get(package_id)
    for resource in package.resources:
        if 'protocol' in resource.extras and 'parent_resource' in resource.extras:
            extras = resource.extras
            try:
                toolkit.get_action('resource_show')(None, { 'id':resource.id,'for-view':True })
            except (NotFound):
                continue

            if extras['parent_resource'] == resource_id and ( extras['protocol'].lower() == 'wms' or extras['ogc_type'].lower() == 'wfs'):
                print resource.state
                if resource.state !='active':
                    return False
                spatialized = True
                break
    return spatialized

def file_path_from_url(url):
    """
    Given a file's URL, find the file itself on this system
    """
    pattern = "^(?P<protocol>.+?)://(?P<host>.+?)/.+/(?P<label>.+)$"
    label = re.match(pattern, url).group("label")
    return get_url_for_file(urllib2.unquote(label))

def file_path_from_url_shp(url):
    """
    Given a file's URL, find the file itself on this system
    """
    tmpFolder = "/var/tmp/"
    label = url.rsplit('/', 1)[-1]
    tmpFile = urllib2.urlopen(url)
    with open(tmpFolder+label, 'wb') as fp:
        shutil.copyfileobj(tmpFile, fp)

    return tmpFolder+label

def folder_path_from_package_shp(package_id):
    """
    Given a file's URL, find the file itself on this system
    """
    required = [".shp", ".shx", ".dbf"]
    optional = [".prj", ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih", ".ixs", ".mxs", ".atx", ".cpg", ".xml", ".fix"]
    valid_endings = required+optional
    tmpFolder = "/var/tmp/"+package_id+"/"
    if not path.exists(tmpFolder):
        makedirs(tmpFolder)

    for resource in toolkit.get_action("package_show")(None, {"id": package_id}).get('resources', []):
        url = resource.get("url", {})
        # copy only valid (additional) shapfile
        if not path.splitext(resource.get("url", {}))[1] in valid_endings:
            continue
        pattern = "^(?P<protocol>.+?)://(?P<host>.+?)/.+/(?P<label>.+)$"
        label = url.rsplit('/', 1)[-1]
        tmpFile = urllib2.urlopen(url)
        with open(tmpFolder+label, 'wb') as fp:
            shutil.copyfileobj(tmpFile, fp)


    return tmpFolder

def get_url_for_file(label):
    """
    Returns the URL for a file given it's label.
    """
    bucket = config.get('ckan.storage.bucket', 'default')
    ofs = storage.get_ofs()
    return ofs.get_url(bucket, label).replace("file://", "")

def check_descriptor_only():
    '''
    Return the config option "geoserver.descriptor_only"
    '''
    rd_only = config.get('geoserver.descriptor_only', 'true')
    if rd_only is not None:
        if rd_only == 'true':
            return True
        else:
            return False
    return None

def get_descriptor_name():
    '''
    Return the config option "geoserver.descriptor_name"
    '''
    descriptor_name = config.get('geoserver.descriptor_name', 'schema_descriptor')
    return descriptor_name

def shapefile_publishing_requirements_fulfiled(package_id):
    '''
    Ckeck if the given package fulfils the minimum needs to publish the shapefile. This is a check on the existence of the mandatory file extensions .shp, .shx, .dbf
    '''
    required = [".shp", ".shx", ".dbf"]
    optional = [".prj", ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih", ".ixs", ".mxs", ".atx", ".cpg", ".xml", ".fix"]
    valid_endings = required+optional

    extensions = []
    for resource in toolkit.get_action("package_show")(None, {"id": package_id}).get('resources', []):
        if not path.splitext(resource.get("url", {}))[1] in valid_endings:
            continue
        extensions.append(path.splitext(resource.get("url", {}))[1])

    # Check that all the required extensions are there
    if len([ext for ext in required if ext in extensions]) == len(required):
        # Check that there are not extension in there that are not required
        if len([ext for ext in extensions if ext in optional]) == len(extensions) - len(required):
            return True

def update_package_published_status(package_id, status):
    '''
    Updates ths published status for a given package_id
    status:
        True -> set published status to true
        False -> set published status to false
    '''

    pkg = toolkit.get_action('package_show')(None, {'id': package_id})
    extras = pkg.get('extras', [])
    for extra in extras:
        key = extra.get('key', None)
        if key == 'published':
            extras.remove(extra)

    tags = pkg.get('tags')

    if status:
        tags.append({'name':'published'})
        new_dict = {u'key': u'published', u'value': u'true'}
    else:
        for tag in tags:
            if tag['name'] == "published":
                tags.remove(tag)
        new_dict = {u'key': u'published', u'value': u'false'}
    extras.insert(0,new_dict)

    toolkit.get_action('package_patch')(None, {'id': package_id, 'extras':extras, 'tags': tags})

    return True

def geoserver_rasters_to_publish(package_id):
    '''
    Ckeck if the given package fulfils the minimum needs to publish the rasterfile.
    '''
    valid_endings = ["geotiff"]

    # Look at the file extensions in the zipfile
    extensions = []
    # extensions = [path.splitext(info.filename)[1] for info in zf.infolist()]
    # go get resources
    for resource in toolkit.get_action("package_show")(None, {"id": package_id}).get('resources', []):
        extensions.append(resource.get("format", {}))

    for ending in extensions:
        for valid in valid_endings:
            if ending==valid:
                return True