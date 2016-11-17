import logging
import ckan.logic as logic
from ckanext.geoserver.model.Geoserver import Geoserver
from ckanext.geoserver.model.Layer import Layer
from ckanext.geoserver.model.ProcessOGC import HandleWMS
from ckan.plugins import toolkit
from pylons.i18n import _
import ckan.lib.helpers as h
from ckan import model
import socket
import sys

log = logging.getLogger(__name__)
_get_or_bust = logic.get_or_bust


def publish_ogc(context, data_dict):
    """
    Publishes the resource details as a Geoserver layer based on the input details.
    If the layer creation is successful then returns "Success" msg, otherwise raises an Exception.
    """

    # Gather inputs
    resource_id = data_dict.get("resource_id", None)
    layer_name = data_dict.get("layer_name", resource_id)
    username = context.get("user", None)
    package_id = data_dict.get("package_id", None)
    join_key = data_dict.get("join_key", None)
    lat_field = data_dict.get("col_latitude", None)
    lng_field = data_dict.get("col_longitude", None)
    datastore = data_dict.get("geoserver_datastore", None)
    layer_version = data_dict.get("layer_version", None)
    workspace_name = data_dict.get("workspace_name", None)
    api_call_type = context.get("api_call_type", "ui")


    # Check that you have everything you need
    if None in [resource_id, layer_name, username, package_id, layer_version, workspace_name]:
        raise Exception(toolkit._("Not enough information to publish resource"))


    # Publish a layer
    def pub():
        log.info("pub.1")
        layer = Layer.publish(package_id, resource_id, workspace_name, layer_name, layer_version, username, datastore, lat_field=lat_field, lng_field=lng_field, join_key=join_key)
        log.info("pub.2")
        return layer

    try:
        l = pub()
        if l is None:
            log.debug("Failed to generate a Geoserver layer.")
            if api_call_type == 'ui':
                h.flash_error(_("Failed to generate a Geoserver layer."))
            raise Exception(toolkit._("Layer generation failed"))
        else:
            # csv content should be spatialized or a shapefile uploaded, Geoserver updated, resources appended.
            #  l should be a Layer instance. Return whatever you wish to
            log.debug("This resource has successfully been published as an OGC service.")
            if api_call_type == 'ui':
                h.flash_success(_("This resource has successfully been published as an OGC service."))
            return {"success": True, "message": _("This resource has successfully been published as an OGC service.")}
    except socket.error:
        log.debug("Error connecting to Geoserver.")
        if api_call_type == 'ui':
            h.flash_error(_("Error connecting to Geoserver."))

        # Confirm that everything went according to plan


def unpublish_ogc(context, data_dict):
    """
    Un-publishes the Geoserver layer based on the resource identifier. Retrieves the Geoserver layer name and package
     identifier to construct layer and remove it.
    """
    resource_id = data_dict.get("resource_id", None)
    layer_name = data_dict.get("layer_name", None)
    username = context.get('user')
    api_call_type = data_dict.get("api_call_type", "ui")
    package_id = data_dict.get("package_id", None)
    if resource_id == 'resource_descriptor_multi' or resource_id == 'shapefile_multi':
        file_resource = toolkit.get_action("package_show")(None, {"id": package_id})
    else:
        file_resource = toolkit.get_action("resource_show")(None, {"id": resource_id})

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

    log.debug("This resource has successfully been unpublished.")
    if api_call_type == 'ui':
        h.flash_success(_("This resource has successfully been unpublished."))
    return {"success": True, "message": _("This resource has successfully been unpublished.")}

def map_search_wms(context, data_dict):
    def wms_resource(resource):
        if resource.get("protocol", {}) == "OGC:WMS":
            return True
        else:
            return False

    def get_wms_data(resource):
        resourceURL = resource.get("url", {})
        this_wms = HandleWMS(resourceURL)
        return this_wms.get_layer_info(resource)
    try:
        pkg_id = data_dict.get("pkg_id")
        pkg = toolkit.get_action("package_show")(None, {'id': pkg_id})
        resources = filter(wms_resource, pkg.get('resources'))

        this_data = map(get_wms_data, resources)

        return this_data
    except:
        return [{'ERROR':'SERVER_ERROR'}]
