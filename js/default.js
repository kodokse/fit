function reloadTable(tab) {
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      var el = document.getElementById(tab);
      el.innerHTML = req.responseText;
    }
  }
  req.open("GET", "http://localhost:" + window.location.port + "/api/status/" + tab, true);
  req.send(null);
}

function reloadDb() {
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {}
  req.open("GET", "http://localhost:" + window.location.port + "/api/reload/", true);
  req.send(null);
}

function selectStatus(status) {
  var se = document.getElementById("frm-Status")
  for (var i = 0; i < se.children.length; ++i) {
    if(se.children[i].value == status) {
      se.selectedIndex = i;
      break;
    }
  }
}

function openAdd(status) {
  document.getElementById("add_issue").style.display = "block";
  selectStatus(status);
}
function closeAdd() {
  document.getElementById("add_issue").style.display = "none";
}
function closeIssue() {
  hideEdit();
  document.getElementById("view_issue").style.display = "none";
}
function showEdit(status) {
  document.getElementById("edit_issue").style.display = "inline";
  selectStatus(status);
}
function hideEdit() {
  document.getElementById("edit_issue").style.display = "none";
}
function toggleEdit(status) {
  var el = document.getElementById("edit_issue");
  if(el.style.display == "inline") {
    hideEdit();
    document.getElementById("btn-edit").innerText = "Edit";
  } else {
    showEdit(status);
    document.getElementById("btn-edit").innerText = "Close";
  }
}

function showIssue(issue) {
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      var el = document.getElementById("view_issue");
      el.innerHTML = req.responseText;
      el.style.display = "block";
    }
  }
  req.open("GET", "http://localhost:" + window.location.port + "/api/issue/" + issue, true);
  req.send(null);
}

function refreshIssue(issue) {
  var el = document.getElementById("view_issue");
  if(el.style.display == "none") {
    return;
  }
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      var el = document.getElementById("view_issue");
      el.innerHTML = req.responseText;
      el.style.display = "block";
    }
  }
  req.open("GET", "http://localhost:" + window.location.port + "/api/issue/" + issue, true);
  req.send(null);
}

function submitIssue(issueId) {
  var matchElem = "Status";
  var table = "";
  var optElems = ["Type", "Status"];
  var txtElems = ["Title", "Description", "Id"]
  var reqText = "";
  var sep = "";
  optElems.forEach(function(oe) {
    var elem = document.getElementById("frm-" + oe);
    reqText += sep + oe + "=" + elem.children[elem.selectedIndex].value;
    if(oe == matchElem) {
      table = elem.children[elem.selectedIndex].value;
    }
    sep = "&";
  });
  txtElems.forEach(function(te) {
    var el = document.getElementById("frm-" + te);
    if(el != null) {
      reqText += sep + te + "=" + el.value;
    }
  });
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      document.getElementById("frm-add").reset();
      reloadTable(table);
      if(issueId != null) {
        refreshIssue(issueId);
      }
    }
  }
  req.open("POST", "http://localhost:" + window.location.port + "/api/add", true);
  req.send(reqText);
}

function submitComment(issue) {
  var matchElem = "Status";
  var txtElems = ["Title", "Description"]
  var reqText = "Type=Comment&Parent=" + issue;
  txtElems.forEach(function(te) {
    var el = document.getElementById("comment-" + te);
    if(el != null) {
      reqText += "&" + te + "=" + el.value;
    }
  });
  var req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if(this.readyState == 4 && this.status == 200) {
      document.getElementById("frm-comment").reset();
      showIssue(issue);
    }
  }
  req.open("POST", "http://localhost:" + window.location.port + "/api/add", true);
  req.send(reqText);
}
