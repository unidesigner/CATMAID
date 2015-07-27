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
  makeMemoryInputOptions: function() {
    return {
      customBG: '#222',
      margin: '4px -2px 0',
      doRender: 'div div',

      buildCallback: function($elm) {
        var colorInstance = this.color;
        var colorPicker = this;
        var random = function(n) {
          return Math.round(Math.random() * (n || 255));
        };

        $elm.prepend('<div class="cp-panel">' +
          'R <input type="text" class="cp-r" /><br>' +
          'G <input type="text" class="cp-g" /><br>' +
          'B <input type="text" class="cp-b" /><hr>' +
          'H <input type="text" class="cp-h" /><br>' +
          'S <input type="text" class="cp-s" /><br>' +
          'B <input type="text" class="cp-v" /><hr>' +
          '<input type="text" class="cp-HEX" />' +
        '</div>').on('change', 'input', function(e) {
          var value = this.value,
            className = this.className,
            type = className.split('-')[1],
            color = {};

          color[type] = value;
          colorInstance.setColor(type === 'HEX' ? value : color,
            type === 'HEX' ? 'HEX' : /(?:r|g|b)/.test(type) ? 'rgb' : 'hsv');
          colorPicker.render();
          this.blur();
        });

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
        '.cp-color-picker{box-sizing:border-box; width:233px;}' +
        '.cp-color-picker .cp-panel {line-height: 21px; float:right;' +
          'padding:0 1px 0 8px; margin-top:-1px; overflow:visible}' +
        '.cp-xy-slider:active {cursor:none;}' +
        '.cp-panel, .cp-panel input {color:#bbb; font-family:monospace,' +
          '"Courier New",Courier,mono; font-size:12px; font-weight:bold;}' +
        '.cp-panel input {width:28px; height:12px; padding:2px 3px 1px;' +
          'text-align:right; line-height:12px; background:transparent;' +
          'border:1px solid; border-color:#222 #666 #666 #222;}' +
        '.cp-panel hr {margin:0 -2px 2px; height:1px; border:0;' +
          'background:#666; border-top:1px solid #222;}' +
        '.cp-panel .cp-HEX {width:52px; position:absolute; margin:1px -3px 0 -2px;}' +
        '.cp-alpha {width:155px;}' +
        '.cp-memory {margin-bottom:6px; clear:both;}' +
        '.cp-memory div {float:left; width:17px; height:17px; margin-right:2px;' +
          'background:rgba(0,0,0,1); text-align:center; line-height:17px;}' +
        '.cp-memory .cp-store {width:21px; margin:0; background:none; font-weight:bold;' +
          'box-sizing:border-box; border: 1px solid; border-color: #666 #222 #222 #666;}',

      renderCallback: function($elm, toggled) {
        var colors = this.color.colors.RND,
          modes = {
            r: colors.rgb.r, g: colors.rgb.g, b: colors.rgb.b,
            h: colors.hsv.h, s: colors.hsv.s, v: colors.hsv.v,
            HEX: this.color.colors.HEX
          };

        $('input', '.cp-panel').each(function() {
          this.value = modes[this.className.substr(3)];
        });
      }
    };
  },

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
