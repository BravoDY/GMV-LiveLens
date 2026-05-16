$(document).ready(function() {

  $.ajax({
    url: `https://assets.diantoushi.com/diantoushi/vendors_popup.js?_d=${new Date().getDate()}`,
    dataType: "text",
    success: function (res) {
      eval.call(window, res);
      window.dts_popup();
    }
  });

});