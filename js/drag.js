function allowDrop(ev) {
  ev.preventDefault();
  ev.dataTransfer.dropEffect = 'move';
}
function drag(ev) {
  ev.dataTransfer.effectAllowed = 'move';
  ev.dataTransfer.setData("text", ev.target.id);
}
function postDrop(todoid, statusid, beforeid) {
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {}
  req.open("GET", "http://localhost:" + window.location.port + "/api/move/" + todoid + "/" + statusid + "/" + beforeid, true);
  req.send(null);
}
function drop(ev) {
  var data = ev.dataTransfer.getData("text");
  ev.preventDefault();
  var target = ev.target;
  var before = ev.target.firstChild;
  target = ev.target;
  while(target.className != "flyb-column") {
    before = target;
    target = target.parentElement;
  }
  target.insertBefore(document.getElementById(data), before);
  postDrop(data, target.id, before.id);
}
