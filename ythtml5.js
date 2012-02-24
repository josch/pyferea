/*
 * inspired by http://userscripts.org/scripts/show/116935
 * by http://userscripts.org/users/miguillo
 */

function transform() {
  nodes = document.getElementsByTagName("object");
  for (i=0; i<nodes.length; i++) {
    transformNode(nodes[i]);
  }

  nodes = document.getElementsByTagName("embed");
  for (i=0; i<nodes.length; i++) {
    if (node.parentNode.nodeName.toLowerCase() == "object") {
      continue;
    }
    transformNode(nodes[i]);
  }
}

function transformNode(node) {
  var embedChild = null;
  if (node.nodeName.toLowerCase() == "object") {
    // it can contains an <embed>
    var children = node.childNodes;
    for ( var j = 0; j < children.length; j++) {
      var child = children[j];
      if (child.nodeName.toLowerCase() == "embed") {
        embedChild = child;
        break;
      }
    }
  }

  var src = node.getAttribute('src'); // case <embed src="xxx">
  if (src == null) { // case <object data="xxx">
    src = node.getAttribute('data');
  }
  if (src == null && embedChild != null) { // case <object><embed src="xx"></object>
    src = embedChild.getAttribute('src');
  }
  if (src == null) {
    return;
  }
  src = src.replace(/^\s+/, '').replace(/\s+$/, '');

  function isZero(s) { return s==null || s=="" || s=="0" || s=="0px"; }

  var width = node.getAttribute('width');
  var height = node.getAttribute('height');

  if (isZero(width) && embedChild != null) width = embedChild.getAttribute('width');
  if (isZero(height) && embedChild != null) height = embedChild.getAttribute('height');

  var nodeStyle = document.defaultView.getComputedStyle(node, "");
  if (isZero(width) && nodeStyle != null) width = nodeStyle.getPropertyValue('width');
  if (isZero(height) && nodeStyle != null) height = nodeStyle.getPropertyValue('height');

  var childStyle = document.defaultView.getComputedStyle(embedChild, "");
  if (isZero(width) && childStyle != null) width = childStyle.getPropertyValue('width');
  if (isZero(height) && childStyle != null) height = childStyle.getPropertyValue('height');

  if (isZero(width)) width = '100%';
  if (isZero(height)) height = '100%';

  var youtubevRegex = /^(?:http:|https:)?\/\/www.youtube.com\/v\/([A-Za-z0-9_-]+)(?:\?(.*))?$/;
  matches = src.match(youtubevRegex);
  if (!matches) {
    return;
  }

  var querystring = "";
  if (matches[2]) {
    querystring = "?"+matches[2];
  }

  var iframe = document.createElement("iframe");

  iframe.setAttribute("class", "youtube-player");
  iframe.setAttribute('type', 'text/html');
  if (width != null) {
    iframe.setAttribute('width', width);
  }
  if (height != null) {
    iframe.setAttribute('height', height);
  }
  iframe.setAttribute('frameborder', 0);

  var src = "//www.youtube.com/embed/" + matches[1] + querystring;
  iframe.setAttribute('src', src);
  node.parentNode.replaceChild(iframe, node);
}

transform();
