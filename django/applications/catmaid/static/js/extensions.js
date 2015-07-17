/* -*- mode: espresso; espresso-indent-level: 2; indent-tabs-mode: nil -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

/**
 * This file is a place for small global extensions of libraries used by CATMAID.
 */


/**
 * jQuery DataTables extensions
 */

/*
 * Sorting function for checkbox column which creates an array of all check box
 * values in a column. Plug-in from:
 * http://datatables.net/plug-ins/sorting/custom-data-source/dom-checkbox
 */
$.fn.dataTable.ext.order['dom-checkbox'] = function (settings, col) {
  return this.api().column(col, {order:'index'}).nodes().map(function (td, i) {
    return $('input', td).prop('checked') ? '1' : '0';
  });
};

/*
 * Sorting function for inputs with a back ground color which reates an array of
 * all background colors.
 */
$.fn.dataTable.ext.order['dom-color-property'] = function (settings, col) {
  return this.api().column(col, {order:'index'}).nodes().map(function (td, i) {
    var c = $(td).attr('data-color');
    return new THREE.Color(c).getHSL();
  });
};

/**
 * Add ascending natural sort string compare type.
 */
$.fn.dataTable.ext.oSort['text-asc']  = function(a, b) {
    return CATMAID.tools.compareStrings(a, b);
};

/**
 * Add descending natural sort string compare type.
 */
$.fn.dataTable.ext.oSort['text-desc']  = function(a, b) {
    return -1 * CATMAID.tools.compareStrings(a, b);
};

/**
 * Add ascending HSL color ordering type.
 */
$.fn.dataTable.ext.oSort['hslcolor-asc']  = function(a, b) {
  return CATMAID.tools.compareHSLColors(a, b);
};

/**
 * Add descending HSL color ordering type.
 */
$.fn.dataTable.ext.oSort['hslcolor-desc']  = function(a, b) {
  return -1 * CATMAID.tools.compareHSLColors(a, b);
};


/**
 * The CATMAID.ColorPicker namespace provides extensions for jQuery
 * tinyColorPicker.
 */

CATMAID.ColorPicker = {
  makeMemoryOptions: function() {
    return {
      customBG: '#222',
      margin: '4px -2px 0',
      doRender: 'div div',
      opacity: true,

      buildCallback: function($elm) {
        var colorInstance = this.color,
          colorPicker = this,
          random = function(n) {
            return Math.round(Math.random() * (n || 255));
          };

        $elm.append('<div class="cp-memory">' +
          '<div></div><div></div><div></div><div></div>' +
          '<div></div><div></div><div></div><div class="cp-store">S</div>').
        on('click', '.cp-memory div', function(e) {
          var $this = $(this);

          if (this.className) {
            $this.parent().prepend($this.prev()).children().eq(0).
              css('background-color', '#' + colorInstance.colors.HEX);
          } else {
            colorInstance.setColor($this.css('background-color'));
            colorPicker.render();
          }
        }).find('.cp-memory div').each(function() {
          !this.className && $(this).css({background:
            'rgb(' + random() + ', ' + random() + ', ' + random() + ')'
          });
        });
      },

      cssAddon: // could also be in a css file instead
        '.cp-memory {margin-bottom:6px; clear:both;}' +
        '.cp-xy-slider:active {cursor:none;}' +
        '.cp-memory div {float:left; width:17px; height:17px; margin-right:2px;' +
          'background:rgba(0,0,0,1); text-align:center; line-height:17px;}' +
        '.cp-memory .cp-store {width:21px; margin:0; background:none; font-weight:bold;' +
          'box-sizing:border-box; border: 1px solid; border-color: #666 #222 #222 #666;}'
    };
  }
};
