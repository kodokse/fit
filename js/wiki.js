function updatePreview() {
  var desc = document.getElementById("desc");
  if(desc == null) {
    return;
  }
  var text = desc.value;
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      document.getElementById("preview").innerHTML = req.responseText;
    }
  }
  req.open("POST", "http://localhost:" + window.location.port + "/api/md", true);
  req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  req.send(text);
}
function savePage(page, redirect) {
  var text = document.getElementById("desc").value;
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(redirect && this.readyState == 4 && this.status == 200) {
      window.location.replace("/wiki/" + page);
    }
  };
  req.open("POST", "http://localhost:" + window.location.port + "/wiki/" + page + "/save", true);
  req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
  req.send(text);
}
function reload() {
  reloadDb();
  updatePreview();
}
