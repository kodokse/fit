# FIT - the Flyweight Issue Tracker

## What is fit?

Fit is a tiny issue tracker with builtin markdown wiki mainly aimed at managing small/medium personal projects.

### Main design goals are:
* Zero config
* Textual database that can be edited by hand and be put under git's control.
* Standalone, dependent only on a web browser and standard Python 3.7 with currently only one additional library: markdown
* No online dependencies (npm etc)
* Be easy to use
* Be fast and have a small footprint

### Intended audience
* Single person teams with a need for an offline issue tracker where they own and control the issue DB without the fuss of setting up and maintaining an enterprise issue tracker (such as Jira, Youtrack, Trac etc)

## Installation

You'll need:
* Python 3.7 (Make sure python is in your path)
* Markdown.py (`$ sudo pip3 install markdown`)
* Clone this repo

For Linux/MacOS
* Put a link to fit.py in `/usr/bin` or `~/bin` or where you typically keep your programs (e.g. `ln -s ~/fit/fit.py ~/bin/fit`)

For Windows
* Add the directory of the fit-repo to your path

## Use

### Linux/MacOS
In the directory of your project type `fit &`.

### Windows
In the directory of your project type `fit.py`.

### General
After starting fit, you can now use your browser to go to `http://localhost` where you will see a simple empty Kanban board. Add issues by clicking on the `+`-sign below the column you want an issue in. By default there are three columns: `Backlog`, `WIP` and `Done`.

### Quitting

`Ctrl-C` works perfectly.

## Additional info

### Background
I was in need of a simple *offline* issue tracker that still allowed me to use it on all separate devices I use for developing my pet projects. I wanted a simple way to access/update my todo-list for a project when I had access to that project. I don't want to maintain a DB or a webserver. I don't want to put all my projects online, in fact I need to be able to work even without access to the internet. The ability to serve up the files in just about any directory with Python's SimpleHTTPServer gave me the idea.

## FAQ

* What if I want to run multiple instances?

    You need to use a different port for fit, e.g. `fit --port 8080 &`

* What if I want my database-file to be called something other than `todo.txt`?

    You can use `fit --file issues.txt &`

* Do I always need to specify command line options if I don't use defaults?

    No, you can type `fit --config --file issues.txt --port 8080 &` the first time for your project then fit will create a `.fit` directory in your project containing a config file. Fit may create a `.fit` directory anyway (even if it currently doesn't).

* Why?

    Why not? Really, if you have to ask, you're most likely not part of the intended audience.
