'use strict';
ckan.module('geoserver_publish_ogc_shp', function($, _) {
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
      id = e.currentTarget.id;
      obj.getExtras(obj.options.package, function(res) {
        obj.extras = res;
        for (var i = 0, emp; i < res.length; i++) {
          if (res[i].key == "published") {
            obj.published = JSON.parse(res[i].value);
          }
        }
        if (obj.options.resource) {
          if (obj.published) {
            obj.sandbox.client.getTemplate('geoserver_unpublish_ogc_form_shp.html', obj.options, obj._onReceiveUnpublishSnippetSingle);
            return true;
          } else {
            obj.sandbox.client.getTemplate('geoserver_publish_ogc_form_shp_single.html', obj.options, obj._onReceivePublishSnippetSingle);
            return true;
          }
        } else {
          if (obj.published) {
            obj.sandbox.client.getTemplate('geoserver_unpublish_ogc_form_shp.html', obj.options, obj._onReceiveUnpublishSnippetMulti);
            return true;
          } else {
            obj.sandbox.client.getTemplate('geoserver_publish_ogc_form_shp_multi.html', obj.options, obj._onReceivePublishSnippetMulti);
            return true;
          }
        }
      });
      return false;
    },
    _onReceivePublishSnippetSingle : function(html) {
      var obj, fields, option, i, selects, resourceInput, packageInput, ogcForm;
      obj = this;
      fields = obj.fieldnames;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val(obj.options.resource);
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
    _onReceivePublishSnippetMulti : function(html) {
      var obj, fields, option, i, selects, resourceInput, packageInput, ogcForm;
      obj = this;
      fields = obj.fieldnames;
      //Make sure removing old modal if exists
      $('#publish_ogc_modal').remove();
      //append new modal into body
      $('body').append(html);
      resourceInput = $('body').find('#resource_id').val("shapefile_multi");
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
            document.location.reload(true)
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
      resourceInput = $('body').find('#resource_id').val(obj.options.resource);
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postUnpublishOGC($(this), function(res) {
            console.log(res);
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
      resourceInput = $('body').find('#resource_id').val("shapefile_multi");
      packageInput = $('body').find('#package_id').val(obj.options.package);
      //show modal
      $('#publish_ogc_modal').modal('show');
      $("#publish_ogc_modal").on('shown', function() {
        ogcForm = $(this).find('form#publish-ogc-form');
        //bind submit event to publish OGC
        ogcForm.submit(function(e) {
          //publish ogc
          obj.postUnpublishOGC($(this), function(res) {
            console.log(res);
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
          console.log(result);
          $('.modal-body .alert').html(result.message).removeClass('alert-info');
          if (result.success) {
            //Success
            $('.modal-body .alert').addClass('alert-success');
            callback(result)
          } else {
            //error
            $('.modal-body .alert').addClass('alert-error');
          }
        },
        error : function(data) {
          console.log(data);
        }
      })
    },
    postSearch : function(id, callback) {
      console.log("geoserver_publish_ogc_shp_postSearch");
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
        },
        error : function(data) {
          console.log(data);
        }
      })
    },
    postUnpublishOGC : function(form, callback) {
      var data, path;
      $('.modal-body .alert').html('Please wait while processing the request ...').addClass('alert-info').css({
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
    parseResponse : function(res) {
      var fields, resFields, i;
      fields = [];
      resFields = res.result.fields;
      for (i = 0; i < resFields.length; i++) {
        fields.push(resFields[i].id);
      }
      return fields;
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
    updatePublishInfo : function(id, status) {
      var path, type, dataType, data, obj;
      obj = this;
      path = '/geoserver/update-package-published-status';
      type = 'POST';
      dataType = 'JSON';
      data = [];
      data.push({
        'name' : 'package_id',
        'value' : id
      });
      data.push({
        'name' : 'status',
        'value' : status
      });
      $.ajax({
        url : path,
        type : type,
        dataType : dataType,
        data : data,
        success : function(response) {
          document.location.reload(true);
          console.log(response);
        },
        error : function(response) {
          console.error(response);
        }
      });
    }
  }
});