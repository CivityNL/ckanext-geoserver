'use strict';
ckan.module('geoserver_publish_ogc_schema_descriptor', function($, _) {
  return {
    initialize : function() {
      var form, res, obj;
      obj = this;
      obj.fieldnames = '';
      $.proxyAll(this, /_on/);
      this.el.on('click', this._onClick);
    },
    _onClick : function(e) {
      var id, obj, fields;
      obj = this;
      obj.getExtras(obj.options.package, function(res) {
        obj.extras = res;
        for (var i = 0, emp; i < res.length; i++) {
          if (res[i].key === obj.options.descriptorname)
            obj.schema_descriptor = JSON.parse(res[i].value);
          if (res[i].key === "published")
            obj.published = JSON.parse(res[i].value);
        }
        if (obj.schema_descriptor.resource_type === "geotiff-timeseries-collection") {
          if (obj.published) {
            obj.sandbox.client.getTemplate('geoserver_unpublish_ogc_form_schema_descriptor.html', obj.options, obj._onReceiveUnpublishSnippetTimeseriesMulti);
            return true;
          } else {
            obj.sandbox.client.getTemplate('geoserver_publish_ogc_form_schema_descriptor_timeseries_multi.html', obj.options, obj._onReceivePublishSnippetTimeseriesMulti);
            return true;
          }
        }
        else if (obj.schema_descriptor.resource_type === "csv-observations-collection") {
          if (obj.schema_descriptor.schema_descriptor_version >= 0.3) {
            for (var i = 0; i < obj.schema_descriptor.members.length; i++) {
              if (obj.schema_descriptor.members[i].resource_type === "observations_with_geometry") {
                obj.options.selected = i;
                if (obj.published) {
                  obj.sandbox.client.getTemplate('geoserver_unpublish_ogc_form_schema_descriptor.html', obj.options, obj._onReceiveUnpublishSnippetSingle);
                  return true;
                } else {
                  obj.sandbox.client.getTemplate('geoserver_publish_ogc_form_schema_descriptor_single.html', obj.options, obj._onReceivePublishSnippetSingle);
                  return true;
                }
                break;
                // else either observations or observed_geometries
              } else if (obj.schema_descriptor.members[i].resource_type == "observations" || obj.schema_descriptor.members[i].resource_type == "observed_geometries")
                if (obj.published) {
                  obj.sandbox.client.getTemplate('geoserver_unpublish_ogc_form_schema_descriptor.html', obj.options, obj._onReceiveUnpublishSnippetMulti);
                  return true;
                } else {
                  obj.sandbox.client.getTemplate('geoserver_publish_ogc_form_schema_descriptor_multi.html', obj.options, obj._onReceivePublishSnippetMulti);
                  return true;
                }
              break;
            }
          }
        }
      });
      return false;
    },
    _onReceivePublishSnippetSingle : function(html) {
      var obj, possibleFields, latfield, lngfield, fields, option, i, selects, resourceInput, packageInput, ogcForm;
      obj = this;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      latfield = $('body').find('#geoserver_lat_field');
      lngfield = $('body').find('#geoserver_lng_field');
      resourceInput = $('body').find('#resource_id').val(obj.schema_descriptor.members[obj.options.selected].resource_name[0]);
      packageInput = $('body').find('#package_id').val(obj.options.package);
      possibleFields = obj.schema_descriptor.members[obj.options.selected].fields;
      for (var i = 0; i < possibleFields.length; i++) {
        if (possibleFields[i].field_role == "latitude") {
          latfield.append($('<option>', {
            value : possibleFields[i].field_id
          }).text(possibleFields[i].field_id));
        }
        if (possibleFields[i].field_role == "longitude") {
          lngfield.append($('<option>', {
            value : possibleFields[i].field_id
          }).text(possibleFields[i].field_id));
        }
      }
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postPublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, true);
          });
          return false;
        });
      });
    },
    _onReceivePublishSnippetMulti : function(html) {
      var obj, possibleFields, joinkey, latfield, lngfield, fields, option, i, selects, resourceInput, packageInput,
        ogcForm;
      obj = this;
      // fields = obj.fieldnames;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      // selects = $('body').find('#geoserver_lat_field, #geoserver_lng_field');
      joinkey = $('body').find('#join_key');
      resourceInput = $('body').find('#resource_id').val("schema_descriptor_multi");
      packageInput = $('body').find('#package_id').val(obj.options.package);
      var observed_geometries_fields = [];
      var observations_fields = [];
      var obs_found = false;
      var geom_found = false;
      var geometries_candidate;
      for (var i = 0; i < obj.schema_descriptor.members.length; i++) {
        if (obs_found && geom_found)
          continue;
        if (obj.schema_descriptor.members[i].resource_type == "observations") {
          obs_found = true;
          for (var j = 0; j < obj.schema_descriptor.members[i].fields.length; j++) {
            observations_fields.push(obj.schema_descriptor.members[i].fields[j].field_id);
          }
        }
        if (obj.schema_descriptor.members[i].resource_type == "observed_geometries") {
          geom_found = true;
          geometries_candidate = i;
          for (var j = 0; j < obj.schema_descriptor.members[i].fields.length; j++) {
            observed_geometries_fields.push(obj.schema_descriptor.members[i].fields[j].field_id);
          }
        }
      }
      for (var i = 0; i < observations_fields.length; i++) {
        for (var j = 0; j < observed_geometries_fields.length; j++) {
          if (observations_fields[i].toLowerCase() == observed_geometries_fields[j].toLowerCase()) {
            joinkey.append($('<option>', {
              value : observations_fields[i].toLowerCase()
            }).text(observations_fields[i].toLowerCase()));
          }
        }
      }
      latfield = $('body').find('#geoserver_lat_field');
      lngfield = $('body').find('#geoserver_lng_field');
      possibleFields = obj.schema_descriptor.members[geometries_candidate].fields;
      for (var i = 0; i < possibleFields.length; i++) {
        if (possibleFields[i].field_role == "latitude") {
          latfield.append($('<option>', {
            value : possibleFields[i].field_id
          }).text(possibleFields[i].field_id));
        }
        if (possibleFields[i].field_role == "longitude") {
          lngfield.append($('<option>', {
            value : possibleFields[i].field_id
          }).text(possibleFields[i].field_id));
        }
      }
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postPublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, true);
          });
          return false;
        });
      });
    },
    _onReceivePublishSnippetTimeseriesMulti : function(html) {
      var obj, resourceInput, packageInput, ogcForm;
      obj = this;
      // fields = obj.fieldnames;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val("schema_descriptor_timeseries_multi");
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postPublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, true);
          });
          return false;
        });
      });
    },
    _onReceiveUnpublishSnippetSingle : function(html) {
      var obj, resourceInput, packageInput, ogcForm;
      obj = this;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val(obj.schema_descriptor.members[obj.options.selected].resource_name[0]);
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postUnpublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, false);
            document.location.reload(true);
          });
          return false;
        });
      });
    },
    _onReceiveUnpublishSnippetTimeseriesMulti : function(html) {
      var obj, resourceInput, packageInput, ogcForm;
      obj = this;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val("schema_descriptor_timeseries_multi");
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postUnpublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, false);
            document.location.reload(true);
          });
          return false;
        });
      });
    },
    _onReceiveUnpublishSnippetMulti : function(html) {
      var obj, resourceInput, packageInput, ogcForm;
      obj = this;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val("schema_descriptor_multi");
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postUnpublishOGC($(this), function(res) {
            obj.updatePublishInfo(obj.options.package, false);
            document.location.reload(true);
          });
          return false;
        });
      });
    },
    postPublishOGC : function(form, callback) {
      var data, path;
      $('.modal-body .alert').html('Please wait while processing the request ...').addClass('alert-info').css({
        'display' : 'block'
      });
      path = '/geoserver/publish-ogc';
      data = form.serializeArray();
      $.ajax({
        url : path,
        type : 'POST',
        dataType : 'JSON',
        data : data,
        success : function(result) {
          $('.modal-body .alert').html(result.message).removeClass('alert-info');
          if (result.success) {
            //Success
            $('.modal-body .alert').addClass('alert-success');
            callback(result)
          } else {
            //error
            $('.modal-body .alert').addClass('alert-error');
          }
        }
      })
    },
    postUnpublishOGC : function(form, callback) {
      var data, path;
      $('.modal-body .alert').html('Please wait while processing the request ... ...').addClass('alert-info').css({
        'display' : 'block'
      });
      path = '/geoserver/unpublish-ogc';
      data = form.serializeArray();
      $.ajax({
        url : path,
        type : 'POST',
        dataType : 'JSON',
        data : data,
        success : function(result) {
          $('.modal-body .alert').html(result.message).removeClass('alert-info');
          if (result.success) {
            //Success
            $('.modal-body .alert').addClass('alert-success');
            callback(result)
          } else {
            //error
            $('.modal-body .alert').addClass('alert-error');
          }
        }
      })
    },
    postSearch : function(id, callback) {
      var path, type, dataType, data;
      path = '/api/action/datastore_search';
      type = 'POST';
      dataType = 'JSON';
      data = JSON.stringify({
        'resource_id' : id
      });
      $.ajax({
        url : path,
        type : type,
        dataType : dataType,
        data : data,
        success : function(response) {
          callback(response);
        }
      })
    },
    getExtras : function(id, callback) {
      var path, type, dataType, data;
      path = '/api/action/package_show';
      type = 'POST';
      dataType = 'JSON';
      data = JSON.stringify({
        'id' : id
      });
      $.ajax({
        url : path,
        type : type,
        dataType : dataType,
        data : data,
        success : function(response) {
          if (response.success) {
            callback(response.result.extras);
          } else {
            return res.error;
          }
        }
      })
    },
    parseResponse : function(res) {
      var fields, resFields, i;
      fields = [];
      resFields = res.result.fields;
      for (i = 0; i < resFields.length; i++) {
        fields.push(resFields[i].id);
      }
      return fields;
    },
    updatePublishInfo : function(id, status) {
      var path, type, dataType, data, obj;
      obj = this;
      path = '/geoserver/update-package-published-status';
      type = 'POST';
      dataType = 'JSON';
      data = [];
      data.push({'name' : 'package_id', 'value' : id});
      data.push({'name' : 'status', 'value' : status});
      $.ajax({
        url : path,
        type : type,
        dataType : dataType,
        data : data,
        success : function(response) {
          document.location.reload(true);
        },
        error : function(response) {
        }
      });
    }
  }
});
