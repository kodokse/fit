#!/usr/bin/python3
import sys
import os
import argparse
import datetime
import hashlib
import urllib
import markdown
import subprocess
from markdown.extensions.wikilinks import WikiLinkExtension
from wsgiref import simple_server, util

class Git(object):
  def __init__(self):
    pass
  def _invoke_git(self, cmd):
    inv = ['git']
    inv.extend(cmd)
    return subprocess.run(inv, capture_output=True)
  def log(self):
    res = self._invoke_git(['log'])
    return res.stdout.decode('utf-8')

def _unescape(s):
  rv = ''
  last = ''
  for c in s:
    if last != '\\':
      if c != '\\':
        rv += c
      last = c
    else:
      if c == 's':
        rv += ';'
      elif c == 'n':
        rv += '\n'
      else:
        rv += c
      last = ''
  return rv

def _escape(s):
  rv = ''
  for c in s:
    if c == ';':
      rv += '\\s'
    elif c == '\n':
      rv += '\\n'
    elif c == '\\':
      rv += '\\\\'
    else:
      rv += c
  return rv

def unescape(s, chars):
  charmap = {'n': '\n', 'r': '\r', 't': '\t'}
  rv = ''
  last = ''
  for c in s:
    if last != '\\':
      if c != '\\':
        rv += c
      last = c
    else:
      tstc = charmap[c] if c in charmap else c
      if tstc in chars:
        rv += tstc
      else:
        rv += '\\'
        rv += c
      last = ''
  return rv

def escape(s, chars):
  charmap = {'\n': 'n', '\r': 'r', '\t': 't'}
  rv = ''
  for c in s:
    if c == '\\':
      rv += '\\\\'
    elif c in chars:
      rv += '\\'
      rv += charmap[c] if c in charmap else c
    else:
      rv += c
  return rv

class FlyEntrySerializer(object):
  def read_all(self, datafile):
    raise NotImplementedError("Should implement")
  def write_all(self, datafile, data):
    raise NotImplementedError("Should implement")

class FlyEntrySerializerVer1(FlyEntrySerializer):
  def __init__(self):
    self.tagreader = {"Config": self._read_config, "Entries": self._read_entries}
  def read_all(self, datafile):
    rv = dict()
    while True:
      tag = datafile.readline().strip().strip('[]')
      if tag in self.tagreader:
        rv[tag] = self.tagreader[tag](datafile)
      else:
        break
    return rv
  def write_all(self, datafile, data):
    print("[Config]", file = datafile)
    for k, v in data["Config"].items():
      print("{}={};".format(k, ';'.join(v)), file = datafile)
    print("[Entries]", file = datafile)
    for r in data["Entries"]:
      print("{};".format(';'.join([_escape(rp) for rp in r[:-1]])), file = datafile)
  def _read_config(self, datafile):
    cfg = dict()
    while True:
      pos = datafile.tell()
      line = datafile.readline()
      if line[0] == '[':
        datafile.seek(pos)
        break
      keyval = line.split('=')
      cfg[keyval[0].strip()] = [v.strip() for v in keyval[1].split(';') if len(v.strip()) > 0]
    return cfg
  def _read_entries(self, datafile):
    rows = []
    while True:
      row = self._read_row(datafile)
      if row == []:
        break
      row.append(len(rows))
      rows.append(row)
    return rows
  def _read_row(self, datafile):
    rawvalues = datafile.readline().split(';')
    values = [_unescape(f.strip()) for f in rawvalues] #if len(f.strip()) > 0]
    return values[:-1]

class FlyEntrySerializerVer2(FlyEntrySerializer):
  def __init__(self):
    self.tagreader = {"Config": self._read_config, "Entries": self._read_entries}
  def read_all(self, datafile):
    rv = dict()
    while True:
      tag = datafile.readline().strip().strip('[]')
      if tag in self.tagreader:
        rv[tag] = self.tagreader[tag](datafile)
      else:
        break
    return rv
  def write_all(self, datafile, data):
    print("[Config]", file = datafile)
    for k, v in data["Config"].items():
      print("{}={};".format(k, ';'.join(v)), file = datafile)
    print("[Entries]", file = datafile)
    for r in data["Entries"]:
      print("\"{}\"\n----".format('\"\n\"'.join([escape(rp, '\"') for rp in r[:-1]])), file = datafile)
  def _read_config(self, datafile):
    cfg = dict()
    while True:
      pos = datafile.tell()
      line = datafile.readline()
      if line[0] == '[':
        datafile.seek(pos)
        break
      keyval = line.split('=')
      cfg[keyval[0].strip()] = [v.strip() for v in keyval[1].split(';') if len(v.strip()) > 0]
    return cfg
  def _read_entries(self, datafile):
    rows = []
    while True:
      row = self._read_row(datafile)
      if row == []:
        break
      row.append(len(rows))
      rows.append(row)
    return rows
  def _read_row(self, datafile):
    values = []
    rawvalues = ''
    while True:
      line = datafile.readline()
      if len(line) == 0:
        return []
      line = line.strip()
      if line == '----' or (len(rawvalues) == 0 and len(line) == 0):
        # done with this entry
        break
      elif len(line) > 0:
        if line[-1] == '\"':
          rawvalues += line.strip('\"')
          values.append(unescape(rawvalues, '\"'))
          rawvalues = ''
        elif line[0] == '\"':
          rawvalues += line[1:]
          rawvalues += '\n'
        else:
          rawvalues += line
          rawvalues += '\n'
      else:
          rawvalues += '\n'
    return values

class FlyDb(object):
  def __init__(self, filename, outver = None):
    self.filename = filename
    self.defaults = {'Id': self._gen_id, 'Created': self._get_date,
                     'Modified': self._get_date, 'Parent': self._return_fixed('none'),
                     'Status': self._return_cfg('Status.Default'), 'Type': self._return_cfg('Type.Default'),
                     'Title': self._return_fixed(''), 'Description': self._return_fixed('')}
    self.serializers = {"1": FlyEntrySerializerVer1(), "2": FlyEntrySerializerVer2()}
    self.inver = ""
    self.outver = outver
    self.rows = []
    self.rowmap = dict()
    self.cfg = self._default_cfg() #{'Status.Default': 'Backlog', 'Type.Default': 'Todo'}
    self.reload_db()
  def _default_cfg(self):
    return {'Status.Default': ['Backlog'],
            'Type.Default': ['Todo'],
            'Type': ['Todo', 'Comment', 'Bug', 'Wiki'],
            'Status': ['Backlog', 'WIP', 'Done'],
            'Status.Color': ['#FF7777', '#77AAFF', '#77FF77'],
            'Type.Color': ['Green', 'Green', 'Red', 'Grey'],
            'Fields': ['Id', 'Type', 'Title', 'Description', 'Created', 'Modified', 'Parent', 'Status']
            }
  def reload_db(self):
    self.rows = []
    self.rowmap = dict()
    self.cfg = self._default_cfg() #self.cfg = {'Status.Default': 'Backlog', 'Type.Default': 'Todo'}
    try:
      with open(self.filename, 'r') as datafile:
        ver = datafile.readline().split('=')
        self.inver = ver[1].strip(' \n')
        ser = self.serializers[self.inver]
        data = ser.read_all(datafile)
        self.cfg = data["Config"]
        self.rows = data["Entries"]
        for r in self.rows:
          self.rowmap[r[0]] = r
    except:
      return False
    return True
  def _gen_id(self):
    return hashlib.sha1((datetime.datetime.today().isoformat() + str(len(self.rows))).encode('utf-8')).hexdigest()[:8].upper()
  def _get_date(self):
    return datetime.datetime.today().isoformat(' ', 'seconds')
  def _return_fixed(self, value):
    return lambda: value
  def _return_cfg(self, cfgval):
    return lambda: self.cfg[cfgval][0]
  def _update_index(self):
    idx = 0
    for r in self.rows:
      r[8] = idx
      idx += 1
  def printall(self):
    for h in self.cfg['Fields']:
      sys.stdout.write("|{}".format(h))
    sys.stdout.write("|\n")
    for r in self.rows:
      for v in r:
        sys.stdout.write("|{}".format(v))
      sys.stdout.write("|\n")
  def write_db(self):
    outver = self.outver
    if outver == None:
      outver = self.inver
    ser = self.serializers[outver]
    with open(self.filename, 'w', newline = '\n') as datafile:
      print("Version={}".format(outver), file = datafile)
      data = {"Config": self.cfg, "Entries": self.rows}
      ser.write_all(datafile, data)
  def get_columns(self):
    return self.cfg['Fields']
  def get_row_count(self):
    return len(self.rows)
  def get_row(self, n):
    return self.rows[n]
  def get_all_rows(self):
    return self.rows
  def _row_match(self, r, type, parent, id, status):
    rv = True
    if type != None:
      if isinstance(type, str):
        rv = rv and r[1].lower() == type.lower()
      else: # assume list
        rv = rv and r[1].lower() in type
    if parent != None:
      rv = rv and r[6].lower() == parent.lower()
    if id != None:
      rv = rv and r[0].lower() == id.lower()
    if status != None:
      rv = rv and r[7].lower() == status.lower()
    return rv
  def _make_dict(self, r, f):
    rv = dict()
    for i in range(len(f)):
      rv[f[i]] = r[i]
    return rv
  def _field_idx(self, name):
    idx = 0
    for n in self.cfg['Fields']:
      if n.lower() == name.lower():
        return idx
      idx += 1
    return -1
  def add_row_from_dict(self, row):
    newrow = []
    for k in self.cfg['Fields']:
      newrow.append(self.defaults[k]())
    newrow.append(len(self.rows))
    for k, v in row.items():
      idx = self._field_idx(k)
      if idx >= 0:
        newrow[idx] = v
    self.rows.append(newrow)
    self.rowmap[newrow[0]] = newrow
  def update_row_from_dict(self, row):
    if not 'Id' in row or not row['Id'] in self.rowmap:
      return False
    dbrow = self.rowmap[row['Id']]
    for k, v in row.items():
      idx = self._field_idx(k)
      if idx >= 0:
        dbrow[idx] = v
    return True
  def get_rows(self, type = None, parent = None, id = None, status = None):
    return [r for r in self.rows if self._row_match(r, type, parent, id, status)]
  def get_rows_as_dict(self, type = None, parent = None, id = None, status = None):
    return [self._make_dict(r, self.cfg['Fields']) for r in self.rows if self._row_match(r, type, parent, id, status)]
  def get_config(self, cfgname):
    return self.cfg[cfgname]
  def get_color_config(self, cfgname):
    return self._make_dict(self.cfg["{}.Color".format(cfgname)], self.cfg[cfgname])
  def change_row(self, id, status = None):
    self.rowmap[id][7] = status
  def place_before(self, id_first, id_after):
    try:
      moving_row = self.rowmap[id_first]
      target_row = self.rowmap[id_after] if id_after != "empty" else self.rows[-1]
      del self.rows[moving_row[8]]
      self.rows.insert(target_row[8], moving_row)
      self._update_index()
    except:
      pass

def query_split(q):
  rv = dict()
  l = q.split('&')
  for a in l:
    k, v = a.split('=')
    rv[k] = urllib.parse.unquote(v)
  return rv

def js_query_split(l):
  rv = dict()
  for a in l:
    k, v = a.split('=')
    rv[k] = urllib.parse.unquote(v)
  return rv

def replace_all(txt, vals):
  rv = ""
  invar = 0
  varname = ""
  for ch in txt:
    if invar == 2:
      if ch == ")":
        try:
          rv += vals[varname]
        except:
          rv += "$({})".format(varname)
        varname = ""
        invar = 0
      else:
        varname += ch
    elif invar == 1:
      if ch == "(":
        invar = 2
      else:
        rv += "$"
        rv += ch
        invar = 0
    else:
      if ch == "$":
        invar = 1
      else:
        rv += ch
  return rv

class FlyServer(object):
  def __init__(self, dbfile, port = 80):
    self.fit_path = sys.path[0]
    self.db = FlyDb(dbfile)
    #self.db.printall()
    self.port = port
    self.option_elems = ['Type', 'Status']
    self.text_elems = [('Title', 'simple'), ('Description', 'multi')]
    self.views = [('Kanban', '/kanban'), ('List', '/list'), ('Wiki', '/wiki'), ('Git', '/git')]
    self.handlers = {'/': self._redirect_to('/kanban'), '/kanban': self._kanban, '/list': self._list, '/wiki': self._wiki, '/git': self._git,
                     '/api': self._api, '/favicon.ico': self._favicon, '/css': self._css, '/js': self._js}
    self.api_handlers = {'status': self._api_status, 'move': self._api_move, 'add': self._api_add, 'reload': self._api_reload,
                         'md': self._api_md, 'issue': self._api_issue}
    self.httpd = simple_server.make_server('', self.port, self._serve)
  def _css(self, args, request_data, environ, respond):
    # '/css/default.css'
    # '/css/'
    # ['css', '']
    with open("{}/css/{}".format(self.fit_path, args[1]), 'rb') as datafile:
      data = datafile.read()
    respond('200 OK', [('Content-Type', 'text/css')])
    return [data]
  def _js(self, args, request_data, environ, respond):
    # '/js/default.js'
    # '/js/WikiPage/wiki.js'
    print("QS: {}".format(args))
    with open("{}/js/{}".format(self.fit_path, args[-1]), 'r') as datafile:
      data = datafile.read()
    respond('200 OK', [('Content-Type', 'text/css')])
    return [replace_all(data, js_query_split(args[1:-1])).encode('utf-8')]
  def _api(self, args, request_data, environ, respond):
    #try:
    f = self.api_handlers[args[1].lower()]
    return f(args[1:], request_data, environ, respond)
    #except KeyError:
    #  print("No handler for {}".format(args[1]))
    #except:
    #  print("Unknown error for {}".format(args[1]))
    respond('404 Not Found', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [b'404 Not Found']
  def _api_add(self, args, request_data, environ, respond):
    qd = query_split(request_data.decode('utf-8'))
    if 'Id' in qd:
      self.db.update_row_from_dict(qd)
    else:
      self.db.add_row_from_dict(qd)
    self.db.write_db()
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [b'']
  def _api_reload(self, args, request_data, environ, respond):
    self.db.reload_db()
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [b'']
  def _api_move(self, args, request_data, environ, respond):
    self.db.change_row(args[1], status = args[2])
    if len(args) > 3:
      self.db.place_before(args[1], args[3])
    self.db.write_db()
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [b'']
  def _api_status(self, args, request_data, environ, respond):
    type_color = self.db.get_color_config("Type")
    doc = ""
    for row in self.db.get_rows_as_dict(type = ['todo', 'bug'], status = args[1]):
      doc += "<div class=\"flyb-blob\" draggable=\"true\" ondragstart=\"drag(event)\" onclick=\"showIssue(\'{}\')\" ".format(row['Id'])
      doc += "id=\"{}\" style=\"background-color: {}\"><div>{}<p class=\"tiny\">{}</p></div></div>".format(row['Id'], type_color[row['Type']], row['Title'], row['Description'])
    doc += "<div id=\"empty\">&nbsp;</div>"
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [doc.encode('utf-8')]
  def _api_md(self, args, request_data, environ, respond):
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [self._encode_wiki(request_data.decode('utf-8')).encode('utf-8')]
  def _api_issue(self, args, request_data, environ, respond):
    doc = ""
    for row in self.db.get_rows_as_dict(type = ['todo', 'bug'], id = args[1]):
      doc += "<div><h3>{}</h3>{}".format(row['Title'], self._encode_wiki(row['Description']))
      doc += "<div style=\"display: none;\" id=\"edit_issue\">"
      doc += "<form method=\"post\" target=\"formtarget\" onsubmit=\"submitIssue(\'{}\')\" id=\"frm-issue\">".format(args[1])
      doc += "\n    <table>\n      <tr>\n"
      for oe in self.option_elems:
        doc += "        <td>{}</td>".format(oe)
      doc += "      </tr>\n      <tr>\n"
      for oe in self.option_elems:
        doc += "        <td><select id=\"frm-{0}\" name=\"{0}\">".format(oe)
        for opt in self.db.get_config(oe):
          doc += "<option value=\"{0}\">{0}</option>".format(opt)
        doc += "</td>\n"
      doc += "      </tr>\n    </table>\n"
      doc += "<input id=\"frm-Id\" type=\"hidden\" value=\"{0}\">".format(row['Id'])
      doc += "<input id=\"frm-Title\" type=\"text\" value=\"{0}\" size=\"60\"><br>".format(row['Title'])
      doc += "<textarea id=\"frm-Description\" cols=\"50\" rows=\"10\">{}</textarea>\n".format(row['Description'])
      doc += "<br><input type=\"submit\" value=\"Save\"></form></div><button id=\"btn-edit\" onclick=\"toggleEdit(\'{}\')\">Edit</button>".format(row['Status'])
      doc += "<h4>Comments</h4>\n"
      for comment in self.db.get_rows_as_dict(type = ['comment'], parent = args[1]):
        doc += "<p class=\"small\">{}</p><p class=\"small\">{}</p>".format(comment['Created'], self._encode_wiki(comment['Description']))
      doc += "<form method=\"post\" target=\"formtarget\" onsubmit=\"submitComment(\'{}\')\" id=\"frm-comment\">".format(args[1])
      doc += "<textarea id=\"comment-Description\" cols=\"50\" rows=\"10\"></textarea>\n"
      doc += "<br><input type=\"submit\" value=\"Add comment\"></form>"
      # add comment form
    doc += "\n</div><div><hr><button onclick=\"closeIssue()\">Close</button></div>\n"
    respond('200 OK', [('Content-Type', 'text/html'), ('Access-Control-Allow-Origin', '*')])
    return [doc.encode('utf-8')]
  def _redirect_to(self, view):
    return lambda args, request_data, environ, respond: self._redirect(view, args, request_data, environ, respond)
  def _redirect(self, view, args, request_data, environ, respond):
    respond('301 Moved Permanently', [('Location', view), ('Access-Control-Allow-Origin', '*')])
    return [b'301 Moved Permanently']
  def _add_header_for(self, self_view):
    doc = "<div class=\"flyb-header\">"
    for v in self.views:
      if v[0].lower() != self_view.lower():
        doc += "<div><a href=\"{}\">{}</a></div>".format(v[1], v[0])
      else:
        doc += "<div>{}</div>".format(v[0])
    doc += "</div>\n"
    return doc
  def _provide_header_for(self, self_view, support_drag_drop = False, additional_scripts = []):
    doc = "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"UTF-8\">\n<title>{}</title>\n".format(self_view)
    doc += "<link rel=\"stylesheet\" href=\"/css/default.css\">\n"
    if support_drag_drop:
      doc += "<link rel=\"stylesheet\" href=\"/css/drag.css\">\n"
    doc += "<script src=\"/js/default.js\"></script>\n"
    if support_drag_drop:
      doc += "<script src=\"/js/drag.js\"></script>\n"
    for s in additional_scripts:
      doc += "<script src=\"/js/{}\"></script>\n".format(s)
    doc += "</head>\n<body onload=\"reload()\">\n"
    doc += self._add_header_for(self_view)
    return doc
  def _text_elem(self, te):
    if te[1] == 'multi':
      return "<textarea id=\"frm-{0}\" name=\"{0}\" rows=\"10\" cols=\"60\"></textarea>".format(te[0])
    return "<input id=\"frm-{0}\" type=\"text\" name=\"{0}\" size=\"60\">".format(te[0])
  def _provide_form_add_html(self):
    doc = "\n<iframe width=\"0\" height=\"0\" border=\"0\" name=\"formtarget\" id=\"formtarget\"></iframe>"
    doc += "\n<div id=\"add_issue\" class=\"overlay\">\n<div class=\"flyb-form\"><h2>Add issue</h2>\n<div class=\"flyb-header\">\n" \
           "<form id=\"frm-add\" onsubmit=\"submitIssue(null)\" target=\"formtarget\" method=\"post\">\n    <table>\n      <tr>\n"
    for oe in self.option_elems:
      doc += "        <td>{}</td>".format(oe)
    doc += "      </tr>\n      <tr>\n"
    for oe in self.option_elems:
      doc += "        <td><select id=\"frm-{0}\" name=\"{0}\">".format(oe)
      for opt in self.db.get_config(oe):
        doc += "<option value=\"{0}\">{0}</option>".format(opt)
      doc += "</td>\n"
    doc += "      </tr>\n    </table>\n"
    for te in self.text_elems:
      doc += "    <div>{0}</div>{1}<br>".format(te[0], self._text_elem(te))
    doc += "    <input type=\"submit\" value=\"Add issue\" onclick=\"closeAdd()\">&nbsp;<input type=\"reset\" value=\"Cancel\" onclick=\"closeAdd()\">\n"
    doc += "  </form>\n  </div>\n</div></div>"
    return doc
  def _kanban(self, args, request_data, environ, respond):
    status_color = self.db.get_color_config("Status")
    all_status = self.db.get_config("Status")
    doc = self._provide_header_for('Kanban', True, ['kanban.js'])
    doc += "\n<div id=\"view_issue\" class=\"overlay\"></div>"
    doc += self._provide_form_add_html()
    doc += "<div class=\"flyb-title\">"
    for s in all_status:
      doc += "<div class=\"flyb-column\"><div>{}</div></div>".format(s)
    doc += "</div>\n<div class=\"flyb-row\">\n"
    for s in all_status:
      doc += "<div class=\"flyb-column\" ondrop=\"drop(event)\" ondragover=\"allowDrop(event)\" id=\"{}\" style=\"background-color: {};\">\n".format(s, status_color[s])
      doc += "</div>\n"
    doc += "</div>\n<div class=\"flyb-title\">"
    for s in all_status:
      doc += "<div><div id=\"add-{0}\" class=\"flyb-button\" style=\"width: 310px;\" onclick=\"openAdd(\'{0}\')\">+</div></div>\n".format(s)
    doc += "</div></body>\n</html>\n"
    respond('200 OK', [('Content-Type', 'text/html')])
    return [doc.encode('utf-8')]
  def _list(self, args, request_data, environ, respond):
    doc = self._provide_header_for('List', False)
    doc += "<table>\n"
    if len(args) == 1:
      for row in self.db.get_rows_as_dict(type = 'todo'):
        doc += "<tr>"
        doc += "<td><a href=\"/list/{}\">{}</a></td>".format(row['Id'], row['Title'])
        doc += "</tr>"
    else:
      doc += "<tr>"
      for c in self.db.get_columns():
        doc += "<td>{}</td>".format(c)
      doc += "</tr>"
      for row in self.db.get_rows(type = 'todo', id = args[1]):
        doc += "<tr>"
        for v in row:
          doc += "<td>{}</td>".format(v)
        doc += "</tr>"
      for row in self.db.get_rows(type = 'comment', parent = args[1]):
        doc += "<tr>"
        for v in row:
          doc += "<td>{}</td>".format(v)
        doc += "</tr>"
    doc += "</table></body></html>"
    respond('200 OK', [('Content-Type', 'text/html')])
    return [doc.encode('utf-8')]
  def _wiki_create(self, args, request_data, environ, respond):
    page = self.db.get_rows_as_dict(type = 'wiki', id = args[1])
    if len(page) == 0:
      row = {'Id': args[1], 'Type': 'Wiki', 'Title': args[1], 'Status': 'none'}
      self.db.add_row_from_dict(row)
      self.db.write_db()
    respond('301 Moved Permanently', [('Location', '/wiki/{}/edit'.format(args[1])), ('Access-Control-Allow-Origin', '*')])
    return [b'301 Moved Permanently']
  def _wiki_save(self, args, request_data, environ, respond):
    row = {'Id': args[1], 'Description': request_data.decode('utf-8')}
    self.db.update_row_from_dict(row)
    self.db.write_db()
    respond('200 OK', [('Content-Type', 'text/html')])
    return [b'']
  def _wiki_edit(self, args, request_data, environ, respond):
    page = self.db.get_rows_as_dict(type = 'wiki', id = args[1])
    doc = self._provide_header_for('Wiki', False, additional_scripts = ["Page={}/wiki.js".format(args[1])])
    doc += "<iframe width=\"0\" height=\"0\" border=\"0\" name=\"formtarget\" id=\"formtarget\"></iframe>"
    doc += "<h2>Edit {}</h2>".format(args[1])
    doc += "<div id=\"preview\"></div>\n"
    doc += "<hr><form target=\"formtarget\" method=\"post\">" \
           "<textarea id=\"desc\" name=\"Description\" rows=\"20\" cols=\"60\" " \
           "onkeyup=\"updatePreview()\" onchange=\"updatePreview()\">{}</textarea><br>".format(page[0]['Description'])
    doc += "\n<button onclick=\"savePage(\'{}\', true)\">Save & Close</button>".format(args[1])
    doc += "<button onclick=\"savePage(\'{}', false)\">Save</button>".format(args[1])
    doc += "<button onclick=\"window.location.replace('/wiki/{0}')\">Cancel</button>\n".format(args[1])
    doc += "</form>"
    doc += "</body></html>"
    respond('200 OK', [('Content-Type', 'text/html')])
    return [doc.encode('utf-8')]
  def _wiki_show(self, args, request_data, environ, respond):
    doc = self._provide_header_for('Wiki' if len(args) < 2 else args[1], False)
    if len(args) == 2:
      page = self.db.get_rows_as_dict(type = 'wiki', id = args[1])
      if len(page) == 0:
        doc += "<hr>\n<button onclick=\"window.location.replace('/wiki/{}/create')\">Create</button>\n".format(args[1])
      else:
      #try:
        doc += self._encode_wiki(page[0]['Description'])
        doc += "<hr>\n<button onclick=\"window.location.replace('/wiki/{}/edit')\">Edit</button>\n".format(args[1])
      #except:
      #  doc += "Doesn't exist"
    else:
      try:
        pages = self.db.get_rows_as_dict(type = 'Wiki')
        for p in pages:
          doc += "<div><a href=\"/wiki/{}\">{}</a></div>".format(p['Id'], p['Id'])
      except:
        doc += "err..."
    doc += "</body></html>"
    respond('200 OK', [('Content-Type', 'text/html')])
    return [doc.encode('utf-8')]
  def _wiki(self, args, request_data, environ, respond):
    wiki_options = {'edit': self._wiki_edit, 'create': self._wiki_create, 'save': self._wiki_save}
    if len(args) > 2:
      return wiki_options[args[2]](args, request_data, environ, respond)
    else:
      return self._wiki_show(args, request_data, environ, respond)
  def _git(self, args, request_data, environ, respond):
    doc = self._provide_header_for('Git', False)
    git = Git()
    doc += "<div>{}</div>".format(self._encode_wiki(git.log()))
    doc += "</body></html>"
    respond('200 OK', [('Content-Type', 'text/html')])
    return [doc.encode('utf-8')]
  def _favicon(self, args, request_data, environ, respond):
    try:
      with open("{}/img/fit.png".format(self.fit_path), 'rb') as datafile:
        data = datafile.read()
      respond('200 OK', [('Content-Type', 'image/png')])
      return [data]
    except:
      respond('404 Not Found', [('Content-Type', 'text/plain')])
      return [b'not found']
  def _serve(self, environ, respond):
    parts = [p for p in environ['PATH_INFO'].split('/') if len(p) > 0]
    if environ['REQUEST_METHOD'] == 'POST':
      try:
        request_body_size = int(environ['CONTENT_LENGTH'])
        request_body = environ['wsgi.input'].read(request_body_size)
      except (TypeError, ValueError):
        request_body = ""
    else:
        request_body = environ['QUERY_STRING']
    #try:
    f = self.handlers['/' + parts[0] if len(parts) > 0 else '/']
    return f(parts, request_body, environ, respond)
    #except KeyError:
    #  respond('404 Not Found', [('Content-Type', 'text/plain')])
    #  return [b'not found']
  def _encode_wiki(self, txt):
    # for now...
    return "{}".format(markdown.markdown(txt, extensions=[WikiLinkExtension(base_url='http://localhost/wiki/')]))
  def serve_forever(self):
    self.httpd.serve_forever()

def main():
  parser = argparse.ArgumentParser(description = 'Flyweight Issue Tracker.')
  parser.add_argument('--config', action = 'store_true', help = 'writes config to .fit/config')
  parser.add_argument('-f', '--file', type = str, dest = 'filename', default = 'todo.txt', help = 'path to database file.')
  parser.add_argument('-p', '--port', type = str, dest = 'port', default = '80', help = 'webserver port')
  args = parser.parse_args()
  flysrv = FlyServer(args.filename, int(args.port))
  #flydb.printall()
  #print("Serving {} on port {}, control-C to stop".format(path, port))
  try:
    flysrv.serve_forever()
  except KeyboardInterrupt:
    print("\b\bShutting down.")

if __name__ == "__main__":
  main()
