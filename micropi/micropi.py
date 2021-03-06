﻿#  micropi.py
#
#  Copyright 2016 Nathan Taylor
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
import gobject
gobject.threads_init()
import pygtk
pygtk.require('2.0')
import gtk
import pango
import pickle
from threading import Thread
import time
import os
from subprocess import PIPE, Popen
from gtksourceview2 import View as SourceView, Mark
import gtksourceview2 as gtkSourceView
from Queue import Queue, Empty
import tempfile
import base64
import tarfile
import platform
import webbrowser
import serial
import serial.tools.list_ports as list_ports
import string
import random
import struct
import errorParser
import json
import sys
import shutil
import fnmatch

SENDIMAGE = False

DARKCOL  = "#242424"
LIGHTCOL = "#E5E5E5"

OPENWINDOWS = []
uBitUploading = False
uBitFound = False
mbedBuilding = False
mbedUploading = False
pipes = None
WORKINGDIR = os.path.dirname(os.path.realpath(__file__))

def printError():
    data = ''
    try:
        d = ['architecture',
             'dist',
             'machine',
             'platform',
             'python_build',
             'python_compiler',
             'python_version',
             'release',
             'system',
             'version',
            ]
        for i in d:
            exec('a=platform.%s()'%i)
            data += str(i) + ' ' +  str(a) + '\n'
        data += '\ngtk ' + str(gtk.ver)
        data += '\nplatform' + str(platform.__version__)
        data += '\ntarfile' + str(tarfile.__version__)
        data += '\npango' + str(pango.version())
        data += '\nglib' + str(gobject.glib_version)
        data += '\npygobject' + str(gobject.pygobject_version)
        data += '\npickle' + str(pickle.__version__)

    except Exception as e:
        print e
    finally:
        print data

class EntryDialog(gtk.Dialog):
    def __init__(self, *args, **kwargs):
        if 'default_value' in kwargs:
            default_value = kwargs['default_value']
            del kwargs['default_value']
        else:
            default_value = ''

        query = args[-1]
        args = args[:-1]

        super(EntryDialog, self).__init__(*args, **kwargs)

        label = gtk.Label(query)
        self.vbox.pack_start(label, True, True)

        entry = gtk.Entry()
        entry.set_text(str(default_value))
        entry.connect("activate",
                      lambda ent, dlg, resp: dlg.response(resp),
                      self, gtk.RESPONSE_OK)
        self.vbox.pack_end(entry, True, True, 0)
        self.vbox.show_all()
        self.entry = entry

    def set_value(self, text):
        self.entry.set_text(text)

    def run(self):
        result = super(EntryDialog, self).run()
        if result == gtk.RESPONSE_OK:
            text = self.entry.get_text()
        else:
            text = None
        return text

class FolderDialog(gtk.MessageDialog):
    def __init__(self, *args, **kwargs):
        if 'default_value' in kwargs:
            default_value = kwargs['default_value']
            del kwargs['default_value']
        else:
            default_value = ''
        super(FolderDialog, self).__init__(*args, **kwargs)

        fcb1 = gtk.FileChooserButton(title="Set BBC Micro:Bit Location")
        fcb1.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)

        self.vbox.pack_end(fcb1, True, True, 0)
        self.vbox.show_all()

        self.fcb1 = fcb1

    def set_value(self, text):
        self.entry.set_text(text)

    def run(self):
        result = super(FolderDialog, self).run()
        if result == gtk.RESPONSE_OK:
            text = self.fcb1.get_filename()
        else:
            text = None
        return text

def message(message, parent=None):
    dia = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, message)
    dia.show()
    dia.run()
    dia.destroy()
    return False

def ask(query, parent=None):
    dia = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, query)
    dia.show()
    rtn=dia.run()
    dia.destroy()
    return rtn == gtk.RESPONSE_YES

def askQ(query, prompt=None, parent=None):
    if prompt:
        dia = EntryDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, query, default_value=prompt)
    else:
        dia = EntryDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, query)
    dia.show()
    rtn=dia.run()
    dia.destroy()
    return rtn

def askFolder(query, prompt=None, parent=None):
    if prompt:
        dia = FolderDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK, query, default_value=prompt)
    else:
        dia = FolderDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK, query)
    dia.show()
    rtn=dia.run()
    dia.destroy()
    return rtn

def uBitPoller():
    global uBitFound
    global uBitUploading
    last = {}
    while True:
        for self in OPENWINDOWS:
            if self not in last:
                last[self] = (False, False)
            uBitFound = os.path.exists(SETTINGS['mbitLocation'])
            if not (uBitUploading and uBitFound):
                if uBitFound and not last[self][0]:
                    gobject.idle_add(self.indicator.set_from_file, os.path.join(WORKINGDIR, "data", "uBitFound.png"))
                elif last[self][0] and not uBitFound:
                    gobject.idle_add(self.indicator.set_from_file, os.path.join(WORKINGDIR, "data", "uBitNotFound.png"))
                    uBitUploading = False
            else:
                gobject.idle_add(self.indicator.set_from_file, os.path.join(WORKINGDIR, "data", "uBitUploading.png"))
            last[self] = (uBitFound, uBitUploading)
        time.sleep(0.2)

def pipePoller(self):
    import sys
    global mbedUploading
    global mbedBuilding
    global uBitUploading
    global uBitFound
    global pipes
    def addText(self, text):
        for self in OPENWINDOWS:
            tb = self.consoleBody.get_buffer()
            tb.insert(tb.get_end_iter(), text)
    bufferdata = ''
    while True:
        if pipes:
            try:
                d1 = pipes[1].readline()
                d2 = pipes[2].readline()
            except UnexpectedEndOfStream:
                pass

            if type(d1) != str:
                d1 = str(d1, encoding="utf-8")
            if type(d2) != str:
                d2 = str(d2, encoding="utf-8")
            sys.stdout.write(d1)
            sys.stdout.write(d2)
            bufferdata += d1 + d2
            sys.stdout.flush()

            gobject.idle_add(addText, self, d1 + d2)

            if not (pipes[1].alive() or pipes[2].alive()):
                errors = errorParser.parse(bufferdata)
                bufferdata = ''

                for e in errors:
                    print 'Error:', e
                    gobject.idle_add(self.message, """Error in file %s!
At line %d, index %d:

%s""" % e)
                pipes = None
                mbedBuilding = False
                os.chdir(WORKINGDIR)
                if os.path.exists('%s/build/bbc-microbit-classic-gcc/source/microbit-build-combined.hex' % buildLocation):
                    gobject.idle_add(addText, self, "Done!\n")
                    if mbedUploading and uBitFound:
                        uBitUploading = True
                        gobject.idle_add(addText, self, "Uploading!\n")
                        thread = Thread(target=upload, args=(self,))
                        thread.daemon = True
                        thread.start()
                    elif mbedUploading:
                        uBitUploading = False
                        mbedUploading = False
                        gobject.idle_add(self.message, """Cannot upload!
Micro:Bit not found!
Check it is plugged in and
Micro:Pi knows where to find it.""")
                else:
                    uBitUploading = False
                    mbedUploading = False
            time.sleep(0.1)
        else:
            time.sleep(0.1)

def upload(self):
    global mbedUploading
    if os.path.exists('%s/build/bbc-microbit-classic-gcc/source/microbit-build-combined.hex' % buildLocation):
        if os.path.exists(SETTINGS['mbitLocation']):
            end = open('%s/build/bbc-microbit-classic-gcc/source/microbit-build-combined.hex' % buildLocation).read()
            open(
                '%s/microbit-build-combined.hex' % SETTINGS['mbitLocation'],
                'w'
            ).write(end)
        else:
            gobject.idle_add(self.message, """Cannot upload!
Micro:Bit not found!
Check it is plugged in and
Micro:Pi knows where to find it.""")
    else:
        gobject.idle_add(self.message, """No build files avaliable""")
    mbedUploading = False

def updateTitle():
    lastTitle = {}
    while True:
        for self in OPENWINDOWS:
            start = '*' if self.getModified() else ''
            fn = os.path.basename(self.saveLocation)
            full = os.path.dirname(self.saveLocation)
            end = 'Micro:Pi'

            title = '%s%s - %s - %s' % (start, fn, full, end)

            if self not in lastTitle:
                lastTitle[self] = ''
            if title != lastTitle[self]:
                gobject.idle_add(self.window.set_title, title)

            lastTitle[self] = title

        time.sleep(0.1)

def serialPoller(self):
    start = True
    def addText(self, text):
        tb = self.consoleBody.get_buffer()
        tb.insert(tb.get_end_iter(), text)
    while True:
        if self.serialConnection:
            try:
                data = self.serialConnection.read()
                d2 = ''
                for i in data:
                    if i in string.printable:
                        d2 += i
                gobject.idle_add(addText, self, d2)
            except:
                pass
        else:
            try:
                self.serialConnection = serial.serial_for_url(self.serialLocation)
                self.serialConnection.baudrate = self.baudrate
            except:
                pass
            time.sleep(0.1)

def inlineSerialPoller(self):
    start = True
    def addText(self, text):
        tb = self.serialConsoleBody.get_buffer()
        tb.insert(tb.get_end_iter(), text)
    while True:
        if self.serialConnection:
            try:
                data = self.serialConnection.read()
                d2 = ''
                for i in data:
                    if i in string.printable:
                        d2 += i
                gobject.idle_add(addText, self, d2)
            except:
                pass
        else:
            try:
                self.serialConnection = serial.serial_for_url(self.serialLocation)
                self.serialConnection.baudrate = self.baudrate
            except:
                pass
            time.sleep(0.1)

def loadSettings():
    return json.load(open(configLocation))

def loadConfig(path):
    d = open(path).read()
    data = {}
    for line in d.split('\n'):
        if line:
            a, b = line.split('=')
            a = a.strip()
            b = b.strip()
            if a not in data:
                data[a] = b
            else:
                data[a] += '\n' + b
    return data

def saveSettings():
    json.dump(SETTINGS, open(configLocation, 'w'),
              sort_keys=True, indent=4, separators=(',', ': '))

def delFolder(path):
    if os.path.exists(path):
        for i in os.listdir(path):
            if os.path.isdir(os.path.join(path, i)):
                delFolder(os.path.join(path, i))
                os.rmdir(os.path.join(path, i))
            else:
                os.remove(os.path.join(path, i))

def setupBEnv():
    #tf = tarfile.open("buildenv.tar.gz", 'r:gz')
    #tf.extractall(MICROPIDIR)
    _dir = os.getcwd()
    os.chdir(MICROPIDIR)
    os.mkdir("microbit-build")
    os.chdir("microbit-build")
    os.system("yotta -n init")
    os.system("yotta target bbc-microbit-classic-gcc")
    os.system("yotta install lancaster-university/microbit")
    d = json.load(open("module.json"))
    d["bin"] = "./source"
    json.dump(d, open("module.json", "w"), sort_keys=True, indent=4, separators=(',', ': '))
    os.chdir("..")
    shutil.move("microbit-build", "buildEnv")
    os.chdir(_dir)

class NBSR:
    """
    A wrapper arround PIPES to make them easier to use
    """

    def __init__(self, stream, parent):
        self._s = stream
        self._q = Queue()
        self._a = True
        self.__a = True
        self._p = parent

        def _populateQueue(stream, queue):
            while self.__a:
                line = stream.readline()
                if type(line) == str:
                    queue.put(line)
        def _killWhenDone(parent):
            parent.wait()
            self.__a = False
            data = self._s.read()
            self._q.put(data)
            while not self._q.empty():
                pass
            self._a = False

        self._t = Thread(
            target=_populateQueue,
            args=(self._s, self._q)
        )
        self._t.daemon = True
        self._t.start()

        self._t2 = Thread(
            target=_killWhenDone,
            args=(self._p,)
        )
        self._t2.daemon = True
        self._t2.start()

    def readline(self, timeout=None):
        try:
            return self._q.get(
                block=timeout is not None,
                timeout=timeout
            )
        except Empty:
            return ''

    def alive(self):
        return self._a

class UnexpectedEndOfStream(BaseException):
    pass



class MainWin:
    def __init__(self, fileData=None):
        self.active = True
        mgr = gtkSourceView.style_scheme_manager_get_default()
        self.style_scheme = mgr.get_scheme('tango' if SETTINGS['theme']=='light' else 'oblivion')
        self.language_manager = gtkSourceView.language_manager_get_default()
        self.languages = {}
        for i in self.language_manager.get_language_ids():
            self.languages[i] = self.language_manager.get_language(i)
        self.filetypes = loadConfig(os.path.join(WORKINGDIR, "data", "filetypes.conf"))

        self.window = gtk.Window()
        self.fullscreenToggler = FullscreenToggler(self.window)
        self.window.connect_object('key-press-event', FullscreenToggler.toggle, self.fullscreenToggler)
        self.window.set_title('Micro:Pi')
        self.window.set_icon_from_file(os.path.join(WORKINGDIR, "data", "icon.png"))
        self.window.resize(750, 500)

        self.window.connect("delete_event", self.destroy)

        self.serialConsole = SerialConsole()

        self.baudrate = 115200
        self.ports = list(list_ports.grep(''))
        self.serialLocation =  None
        self.serialConnection = None
        if self.serialLocation is not None:
            self.serialConnection.baudrate = self.baudrate

        thread = Thread(target=inlineSerialPoller, args=(self,))
        thread.daemon = True
        thread.start()


        vbox = gtk.VBox()
        self.window.add(vbox)

        self.tabWidth = 4
        self.autoIndent = True
        self.lineNumbers = True

        self.saveLocation = ''

        self.modified = False

        self.openFiles = []

        if fileData is None:
            self.files = self.loadFilesFromFile(os.path.join(WORKINGDIR, "data", "default.mpi"))
        else:
            self.files = fileData

        ### START MENU ###

        def loadEXPMen(path):
            men = []
            p = os.listdir(path)
            p.sort()
            for i in p:
                if not os.path.isdir(os.path.join(path, i)):
                    if i[-(len(SETTINGS['fileExtention'])+1):] == '.'+SETTINGS['fileExtention']:
                        ni = i[:-(len(SETTINGS['fileExtention'])+1)]
                    else:
                        ni = i
                    men.append((ni, (self.loadExample, '', '', os.path.join(path, i))))
                else:
                    men.append((i, loadEXPMen(os.path.join(path, i))))
            return men

        exampleMenu = loadEXPMen(os.path.join(WORKINGDIR, "examples"))

        menuData = [
                    ("_File", [
                              ("_New Project", (self.newProject, gtk.STOCK_NEW, '<Control>N')),
                              ("Add _Page", (self.newPage, gtk.STOCK_NEW, '')),
                              ("_Examples", exampleMenu),
                              ("_Import File", (self.importFile, gtk.STOCK_ADD, '<Control>I')),
                              ("_Open", (self.openFile, gtk.STOCK_OPEN, '<Control>O')),
                              ("_Save", (self.save, gtk.STOCK_SAVE, '<Control>S')),
                              ("Save _As", (self.saveAs, gtk.STOCK_SAVE_AS, '')),
                              ('', ''),
                              ("_Quit", (self.destroy, gtk.STOCK_QUIT, '<Control>Q'))
                             ]
                    ),
                    ("_Edit", [
                               ("_Undo", (self.sendUndo, gtk.STOCK_UNDO, '<Control>Z')),
                               ("_Redo", (self.sendRedo, gtk.STOCK_REDO, '<Control>Y')),
                               ('', ''),
                               ("Cu_t", (self.sendCut, gtk.STOCK_CUT, '<Control>X')),
                               ("_Copy", (self.sendCopy, gtk.STOCK_COPY, '<Control>C')),
                               ("_Paste", (self.sendPaste, gtk.STOCK_PASTE, '<Control>V')),
                               ('', ''),
                               ("Select _All", (self.sendSelectAll, gtk.STOCK_SELECT_ALL, '<Control>A')),
                               ('', ''),
                               ("Preference_s", (self.showSettings, gtk.STOCK_PREFERENCES, '<Control><Alt>P'))
                              ]
                    ),
                    ("_View", [
                               ("Show _Line Numbers", (self.lineNumbersToggle, '', '', '', 'checkbox', True)),
                               ("Enable Auto _Indent", (self.autoIndentToggle, '', '', '', 'checkbox', True)),
                               ("_Tab Width", [
                                              ("2", (self.setTabWidth, '', '', '', 'radio', False, 'radioGroup1', 2)),
                                              ("4", (self.setTabWidth, '', '', '', 'radio', True, 'radioGroup1', 4)),
                                              ("6", (self.setTabWidth, '', '', '', 'radio', False, 'radioGroup1', 6)),
                                              ("8", (self.setTabWidth, '', '', '', 'radio', False, 'radioGroup1', 8)),
                                              ("10", (self.setTabWidth, '', '', '', 'radio', False, 'radioGroup1', 10)),
                                              ("12", (self.setTabWidth, '', '', '', 'radio', False, 'radioGroup1', 12)),
                                             ]
                               ),
                              ]
                    ),
                    ("_Deploy", [
                                ("_Build", (self.startBuild, gtk.STOCK_EXECUTE, '<Control>B')),
                                ("Build and _Upload", (self.startBuildAndUpload, '', '<Control>U')),
                                ("_Force Upload", (self.forceUpload, gtk.STOCK_DISCONNECT, '')),
                                ('', ''),
                                ("Serial _Monitor", (self.serialConsole.toggleVis, '', '<Control>M'))
                               ]
                    ),
                    ("_Help", [
                               ("_Website", (self.website, gtk.STOCK_HELP, 'F1')),
                               ("_About", (self.showAbout, gtk.STOCK_ABOUT, '')),
                              ]
                    ),
                   ]

        agr = gtk.AccelGroup()
        self.window.add_accel_group(agr)

        def loadMenu(menu, first=True):
            radioGroups = {}
            np = gtk.MenuBar() if first else gtk.Menu()
            for i in menu:
                if i == ('', ''):
                    sep = gtk.SeparatorMenuItem()
                    sep.show()
                    np.append(sep)
                elif type(i[1]) == list:
                    dt = loadMenu(i[1], False)
                    mi = gtk.MenuItem(i[0])
                    mi.show()
                    mi.set_submenu(dt)
                    np.append(mi)
                elif len(i[1]) == 3 or len(i[1]) == 4:
                    dat = i[1]
                    if dat[1]:
                        mi = gtk.ImageMenuItem(dat[1])
                        mi.get_children()[0].set_label(i[0])
                    else:
                        mi = gtk.MenuItem(i[0])
                    if dat[0]:
                        if len(dat) == 3:
                            mi.connect("activate", dat[0])
                        elif len(dat) == 4:
                            mi.connect_object("activate", dat[0], dat[3])
                    if dat[2]:
                        key, mod = gtk.accelerator_parse(dat[2])
                        mi.add_accelerator("activate", agr, key, mod, gtk.ACCEL_VISIBLE)
                    mi.show()
                    np.append(mi)
                elif len(i[1]) > 4:
                    dat = i[1]
                    if dat[4] == "checkbox":
                        mi = gtk.CheckMenuItem(i[0])
                        if len(dat) == 6:
                            mi.set_active(dat[5])
                        if dat[0]:
                            mi.connect("activate", dat[0])
                        mi.show()
                        np.append(mi)
                    elif dat[4] == "radio":
                        mi = gtk.RadioMenuItem(label=i[0])
                        if dat[6] not in radioGroups:
                            radioGroups[dat[6]] = mi
                        else:
                            mi.set_group(radioGroups[dat[6]])
                        if dat[5]:
                            mi.set_active(True)
                        if dat[0]:
                            mi.connect("activate", dat[0], dat[7])
                        mi.show()
                        np.append(mi)
            return np

        self.menu = loadMenu(menuData)
        #self.table.attach(self.menu, 0, 1, 0, 1, yoptions = 0)
        vbox.pack_start(self.menu, False, False)
        self.menu.show()

        ### END MENU ###

        ### START TOOLBAR ###

        self.toolbar = gtk.HBox()

        self.indicator = gtk.Image()
        self.indicator.set_from_file(os.path.join(WORKINGDIR, "data", "uBitNotFound.png"))
        self.toolbar.pack_start(self.indicator, False, False)

        vbox.pack_start(self.toolbar, False, False)

        ### END TOOLBAR ###

        ### START WINDOW BODY ###

        paned1 = gtk.HPaned()



        folderIcon = gtk.Image().render_icon(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_MENU)
        fileIcon = gtk.Image().render_icon(gtk.STOCK_FILE, gtk.ICON_SIZE_MENU)

        self.treeStore = gtk.TreeStore(gtk.gdk.Pixbuf, str, bool)

        # Load files

        def load(dic, parent=None):
            for i, j in dic.items():
                isFile = j[0]
                if isFile:
                    self.treeStore.append(parent, [fileIcon, i, True])
                else:
                    p = self.treeStore.append(parent, [folderIcon, i, False])
                    load(j[1], p)
        load(self.files)

        treeViewScroll = gtk.ScrolledWindow()
        treeViewScroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.treeView = gtk.TreeView(self.treeStore)
        self.treeView.connect('row-activated', self.openInternalFile)
        self.treeView.connect('button-press-event', self.onTreeviewButtonPressEvent)
        self.tvMenuOn = []

        self.filepopup = gtk.Menu()
        for i in ["Open", "Rename", "Delete"]:
            menu_items = gtk.MenuItem(i)
            self.filepopup.append(menu_items)
            menu_items.connect("activate", self.onFilePopup, i)
            menu_items.show()
        self.dirpopup = gtk.Menu()
        for i in ["New File", "New Folder", "Rename", "Delete"]:
            menu_items = gtk.MenuItem(i)
            self.dirpopup.append(menu_items)
            menu_items.connect("activate", self.onFolderPopup, i)
            menu_items.show()
        self.outpopup = gtk.Menu()
        for i in ["New File", "New Folder"]:
            menu_items = gtk.MenuItem(i)
            self.outpopup.append(menu_items)
            menu_items.connect("activate", self.onOutPopup, i)
            menu_items.show()

        (COL_PIXBUF, COL_STRING) = range(2)

        column = gtk.TreeViewColumn()
        column.set_title("Files")
        self.treeView.append_column(column)

        renderer = gtk.CellRendererPixbuf()  # Icon renderer
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', COL_PIXBUF)

        renderer = gtk.CellRendererText()  # Text renderer
        font = pango.FontDescription('10') # Change font size
        renderer.set_property('font-desc', font) # Apply new font
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'text', COL_STRING)

        self.treeView.set_size_request(150, 0)
        treeViewScroll.add(self.treeView)
        paned1.pack1(treeViewScroll, False, False)

        paned2 = gtk.VPaned()

        self.notebook = gtk.Notebook() # File storage notebook
        self.notebook.set_scrollable(True)

        paned2.pack1(self.notebook, True, True)


        thingsNotebook = gtk.Notebook()

        consoleScroll = gtk.ScrolledWindow()
        consoleScroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_ALWAYS)

        txtB = gtkSourceView.Buffer()
        txtB.set_style_scheme(self.style_scheme)
        txtB.set_highlight_matching_brackets(False)
        txtB.set_highlight_syntax(False)
        txtB.place_cursor(txtB.get_start_iter())

        self.consoleBody = SourceView(txtB)
        self.consoleBody.modify_font(pango.FontDescription('Monospace 10'))
        self.consoleBody.set_editable(False)

        consoleScroll.add(self.consoleBody)

        img = gtk.Image()
        img.set_from_icon_name(gtk.STOCK_EXECUTE, 16)
        thingsNotebook.append_page(consoleScroll, img)



        serialVbox = gtk.VBox()

        serialConsoleFrame = gtk.ScrolledWindow()
        serialConsoleFrame.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_ALWAYS)

        txtB2 = gtkSourceView.Buffer()
        txtB2.set_style_scheme(self.style_scheme)
        txtB2.set_highlight_matching_brackets(False)
        txtB2.set_highlight_syntax(False)
        txtB2.place_cursor(txtB2.get_start_iter())

        self.serialConsoleBody = SourceView(txtB2)
        self.serialConsoleBody.modify_font(pango.FontDescription("Monospace 10"))
        serialConsoleFrame.add(self.serialConsoleBody)
        self.serialConsoleBody.set_editable(False)
        serialVbox.pack_start(serialConsoleFrame, 2)

        serialEntryHBox = gtk.HBox()
        self.serialEntry = gtk.Entry()
        serialEntryHBox.pack_start(self.serialEntry, True, True, 2)
        self.serialEntry.connect("activate", self.send)
        sendButton = gtk.Button("Send")
        serialEntryHBox.pack_start(sendButton, False, False, 2)
        sendButton.connect("clicked", self.send)

        serialVbox.pack_start(serialEntryHBox, False, False, 2)

        serialHbox = gtk.HBox()
        gtkbaudrate = gtk.combo_box_new_text()
        gtkbaudrate.append_text("300")
        gtkbaudrate.append_text("1200")
        gtkbaudrate.append_text("2400")
        gtkbaudrate.append_text("4800")
        gtkbaudrate.append_text("9600")
        gtkbaudrate.append_text("19200")
        gtkbaudrate.append_text("38400")
        gtkbaudrate.append_text("57600")
        gtkbaudrate.append_text("115200")
        gtkbaudrate.set_active(8)
        gtkbaudrate.connect("changed", self.brtchange)
        serialHbox.pack_start(gtkbaudrate, False, False)

        serialRefreshButton = gtk.Button("Refresh")
        serialRefreshButton.connect("clicked", self.refresh)
        serialHbox.pack_start(serialRefreshButton, True, False)

        serialClearButton = gtk.Button("Clear")
        serialClearButton.connect("clicked", self.clear)
        serialHbox.pack_start(serialClearButton, True, False)

        #connHBox = gtk.HBox()

        self.gtkserialloc = gtk.combo_box_new_text()
        for i in self.ports:
            self.gtkserialloc.append_text(i[0])
        self.gtkserialloc.set_active(0)

        serialHbox.pack_start(self.gtkserialloc, False, False)

        serialConnectButton = gtk.Button("Connect")
        serialConnectButton.connect("clicked", self.connectToPort)
        serialHbox.pack_start(serialConnectButton, False, False)

        serialVbox.pack_start(serialHbox, False, False, 0)


        img = gtk.Image()
        img.set_from_icon_name(gtk.STOCK_DISCONNECT, 16)
        thingsNotebook.append_page(serialVbox, img)


        thingsNotebook.set_tab_pos(gtk.POS_LEFT)

        paned2.pack2(thingsNotebook, False, True)

        paned1.pack2(paned2, True, True)

        vbox.pack_start(paned1)

        ### END WINDOW BODY ###

        ### START WINDOW COLOURING ###

        self.setTheme(None, SETTINGS['theme'])

        if SETTINGS['theme'] == 'dark':
            colour = gtk.gdk.color_parse(DARKCOL)
        else:
            colour = gtk.gdk.color_parse(LIGHTCOL)

        self.window.modify_bg(gtk.STATE_NORMAL, colour)

        ### END WINDOW COLOURING ###

        self.window.show_all()

        if len(sys.argv) > 1: # Has the user requested to open a file from the command line?
            self.forceOpenFileByFN(sys.argv[1]) # If so, load it

    def refreshTree(self):
        folderIcon = gtk.Image().render_icon(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_MENU)
        fileIcon = gtk.Image().render_icon(gtk.STOCK_FILE, gtk.ICON_SIZE_MENU)

        def load(dic, parent=None):
            for i, j in dic.items():
                isFile = j[0]
                if isFile:
                    self.treeStore.append(parent, [fileIcon, i, True])
                else:
                    p = self.treeStore.append(parent, [folderIcon, i, False])
                    load(j[1], p)
        self.treeStore.clear()
        load(self.files)

    def onFilePopup(self, *args):
        label = args[1]
        listP = self.tvMenuOn
        fullP = "/".join(listP) + "/"
        filename = listP[-1]
        if label == "Open":
            if fullP not in self.openFiles:
                d = self.files
                for i in listP:
                    d = d[i][1]
                self.addNotebookPage(filename, d, fullP)
                self.openFiles.append(fullP)
            else:
                for i in range(self.notebook.get_n_pages()):
                    page = self.notebook.get_nth_page(i)
                    fn = self.notebook.get_tab_label(page).get_tooltip_text()
                    if fn == fullP:
                        self.notebook.set_current_page(i)
        elif label == "Rename":
            name = self.askQ("New Name", prompt=filename, ok="Rename")
            if name is not None:
                nfp = listP[:-1]
                nfp.append(name)
                nfp = "/".join(nfp) + "/"

                if fullP in self.openFiles:
                    self.openFiles.remove(fullP)
                    self.openFiles.append(nfp)

                for i in range(self.notebook.get_n_pages()):
                    page = self.notebook.get_nth_page(i)
                    fn = self.notebook.get_tab_label(page).get_tooltip_text()
                    if fn == fullP:
                        lab = self.notebook.get_tab_label(page)
                        lab.children()[0].set_label(name)
                        lab.set_tooltip_text(nfp)

                d = self.files
                for i in listP[:-1]:
                    d = d[i][1]
                data = d[filename]
                del d[filename]
                d[name] = data

                self.refreshTree()
        elif label == "Delete":
            rem = self.ask("Are you sure you want to delete %s?" % filename)
            if rem:
                if fullP in self.openFiles:
                    self.openFiles.remove(fullP)

                toRemove = None
                for i in range(self.notebook.get_n_pages()):
                    page = self.notebook.get_nth_page(i)
                    fn = self.notebook.get_tab_label(page).get_tooltip_text()
                    if fn == fullP:
                        toRemove = i
                if toRemove is not None:
                    self.notebook.remove_page(toRemove)

                d = self.files
                for i in listP[:-1]:
                    d = d[i][1]
                del d[filename]

                self.refreshTree()

    def onFolderPopup(self, *args):
        label = args[1]
        listP = self.tvMenuOn
        fullP = "/".join(listP) + "/"
        filename = listP[-1]
        if label == "Rename":
            name = self.askQ("New Name", prompt=filename, ok="Rename")
            if name is not None:
                nfp = listP[:-1]
                nfp.append(name)
                nfp = "/".join(nfp) + "/"

                for i in list(self.openFiles):
                    if i.startswith(fullP):
                        np = i[len(fullP):]
                        np = nfp + np

                        print i, np

                        self.openFiles.remove(i)
                        self.openFiles.append(np)

                for i in range(self.notebook.get_n_pages()):
                    page = self.notebook.get_nth_page(i)
                    fn = self.notebook.get_tab_label(page).get_tooltip_text()
                    if fn.startswith(fullP):
                        fn = fn[len(fullP):]
                        fn = nfp + fn

                        lab = self.notebook.get_tab_label(page)
                        lab.set_tooltip_text(fn)

                d = self.files
                for i in listP[:-1]:
                    d = d[i][1]
                data = d[filename]
                del d[filename]
                d[name] = data

                self.refreshTree()
        elif label == "Delete":
            rem = self.ask("Are you sure you want to delete %s?" % filename)
            if rem:
                toRemove = None
                loop = True
                while loop:
                    for i in range(self.notebook.get_n_pages()):
                        page = self.notebook.get_nth_page(i)
                        fn = self.notebook.get_tab_label(page).get_tooltip_text()
                        if fn.startswith(fullP):
                            toRemove = i
                            if fn in self.openFiles:
                                self.openFiles.remove(fn)
                    if toRemove is not None:
                        self.notebook.remove_page(toRemove)
                        toRemove = None
                    else:
                        loop = False

                d = self.files
                for i in listP[:-1]:
                    d = d[i][1]
                del d[filename]

                self.refreshTree()
        elif label == "New File":
            name = self.askQ("New Name", ok="Create")
            if name is not None:
                d = self.files
                for i in listP:
                    d = d[i][1]
                d[name] = [True, ""]

                self.refreshTree()
        elif label == "New Folder":
            name = self.askQ("New Name", ok="Create")
            if name is not None:
                d = self.files
                for i in listP:
                    d = d[i][1]
                d[name] = [False, {}]

                self.refreshTree()

    def onOutPopup(self, *args):
        label = args[1]

        if label == "New File":
            name = self.askQ("New Name", ok="Create")
            if name is not None:
                d = self.files
                d[name] = [True, ""]

                self.refreshTree()
        elif label == "New Folder":
            name = self.askQ("New Name", ok="Create")
            if name is not None:
                d = self.files
                d[name] = [False, {}]

                self.refreshTree()

    def loadFilesFromDir(self, d):
        """
        Loads files from a directory into a format that Micro:Pi recognises
        """
        o = {}
        for i in os.listdir(d):
            p = os.path.join(d, i)
            if os.path.isdir(p):
                o[(i)] = [False, self.loadFilesFromDir(p)]
            else:
                o[(i)] = [True, open(p).read()]
        return o

    def loadFilesFromFile(self, f):
        """
        Loads files from a file into a format that Micro:Pi recognises
        """
        tf = tarfile.open(f)
        tmp = tempfile.mkdtemp()
        tf.extractall(tmp)

        data = self.loadFilesFromDir(tmp)

        shutil.rmtree(tmp)

        return data

    def saveInternalOpenFiles(self):
        for i in range(self.notebook.get_n_pages()):
            page = self.notebook.get_nth_page(i)
            fn = self.notebook.get_tab_label(page).get_tooltip_text()
            fn = fn.split("/")
            while "" in fn:
                fn.remove("")
            d = self.files
            for i in fn:
                if i != fn[-1]:
                    d = d[i][1]

            tb = page.get_child().get_buffer()
            txt = tb.get_text(*tb.get_bounds())

            d[i][1] = txt

    def openInternalFile(self, treeview, path, column):
        model = self.treeView.get_model()

        _iter = model.get_iter(path)
        filename = model.get_value(_iter, 1)
        isFile = model.get_value(_iter, 2)

        fullP = ""
        listP = []
        p = path
        while p:
            _iter = model.get_iter(p)
            fn = model.get_value(_iter, 1)
            p = p[:-1]
            fullP = fn + "/" + fullP
            listP = [fn] + listP

        if not isFile:
            if not self.treeView.row_expanded(path):
                self.treeView.expand_row(path, False)
            else:
                self.treeView.collapse_row(path)
        elif fullP not in self.openFiles:
            d = self.files
            for i in listP:
                d = d[i][1]
            self.addNotebookPage(filename, d, fullP)
            self.openFiles.append(fullP)
        else:
            for i in range(self.notebook.get_n_pages()):
                page = self.notebook.get_nth_page(i)
                fn = self.notebook.get_tab_label(page).get_tooltip_text()
                if fn == fullP:
                    self.notebook.set_current_page(i)

    def website(self, *args):
        webbrowser.open("http://bottersnike.github.io/Micro-Pi")

    def showAbout(self, *args):
        dia = gtk.AboutDialog()
        dia.set_property('program-name', 'Micro:Pi')
        dia.set_property('version', '0.0.1')
        dia.set_property('copyright', '(c) Nathan Taylor 2016\nThe words "BBC" and "Micro:Bit" and the BBC Micro:Bit logo are all\ntrademarks of the BBC and I lay no claim to them.')
        dia.set_property('website', 'http://bottersnike.github.io/Micro-Pi')
        dia.set_property('comments', 'A pure python IDE for the BBC:MicroBit for C++')
        dia.set_property('license', open('data", "LICENSE').read())
        dia.show()
        dia.run()
        dia.destroy()
        return False

    def setUBitLoc(self, *args):
        loc = self.askQ("Location:", SETTINGS['mbitLocation'])
        if loc:
            SETTINGS['mbitLocation'] = loc
            saveSettings()

    def sendCopy(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("copy-clipboard")

    def sendPaste(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("paste-clipboard")

    def sendCut(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("cut-clipboard")

    def sendRedo(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("redo")

    def sendUndo(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("undo")

    def sendSelectAll(self, *args):
        s = self.notebook.get_nth_page(self.notebook.get_current_page())
        t = s.get_children()[0]
        t.emit("select-all", 1)

    def toggleQS(self, widget, *args):
        SETTINGS['quickstart'] = widget.get_active()
        saveSettings()

    def autoIndentToggle(self, widget, *args):
        self.autoIndent = widget.get_active()
        for f in self.notebook:
            f.get_child().set_auto_indent(widget.get_active())

    def lineNumbersToggle(self, widget, *args):
        self.lineNumbers = widget.get_active()
        for f in self.notebook:
            f.get_child().set_show_line_numbers(widget.get_active())

    def setTabWidth(self, widget, width, *args):
        if widget.get_active():
            self.tabWidth = width
            for f in self.notebook:
                f.get_child().set_tab_width(width)

    def setTheme(self, widget, theme, *args):
        if widget is None or widget.get_active():
            SETTINGS['theme'] = theme
            saveSettings()
            if SETTINGS['theme'] == 'dark':
                colour = gtk.gdk.color_parse(DARKCOL)
            else:
                colour = gtk.gdk.color_parse(LIGHTCOL)

            for w in OPENWINDOWS:
                w.window.modify_bg(gtk.STATE_NORMAL, colour)

                mgr = gtkSourceView.style_scheme_manager_get_default()
                w.style_scheme = mgr.get_scheme('tango' if SETTINGS['theme']=='light' else 'oblivion')
                for f in self.notebook:
                    f.get_child().props.buffer.set_style_scheme(self.style_scheme)
                w.serialConsole.window.modify_bg(gtk.STATE_NORMAL, colour)
                if SENDIMAGE: w.serialConsole.imageCreator.window.modify_bg(gtk.STATE_NORMAL, colour)
                w.serialConsole.consoleBody.props.buffer.set_style_scheme(w.style_scheme)
                w.consoleBody.props.buffer.set_style_scheme(w.style_scheme)

    def getLanguage(self, title):
        for a, b in self.filetypes.items():
            for i in b.split(';'):
                if fnmatch.filter([title], i):
                    a = a.lower()
                    if a in self.languages:
                        return self.languages[a]
        return None

    def addNotebookPage(self, title, content, path):
        area = gtk.ScrolledWindow()
        area.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_ALWAYS)
        area.show()

        txtB = gtkSourceView.Buffer()
        txtB.begin_not_undoable_action()
        txtB.set_style_scheme(self.style_scheme)

        language = self.getLanguage(title)

        txtB.set_highlight_matching_brackets(True)
        if language is not None:
            txtB.set_highlight_syntax(True)
            txtB.set_language(language)

        txtB.set_text(content)
        txtB.place_cursor(txtB.get_start_iter())
        txtB.set_modified(False)
        txtB.end_not_undoable_action()

        text = SourceView(txtB)
        text.set_tab_width(self.tabWidth)
        text.set_insert_spaces_instead_of_tabs(False)
        text.set_show_right_margin(True)
        text.set_show_line_marks(True)
        text.set_auto_indent(self.autoIndent)
        text.set_show_line_numbers(self.lineNumbers)
        text.show()
        text.modify_font(pango.FontDescription('Monospace 10'))
        area.add(text)


        top = gtk.HBox()

        title = gtk.Label(title)
        title.show()
        top.set_tooltip_text(path)


        top.pack_start(title, True, True, 0)
        butt = gtk.Button()
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        img.show()
        butt.set_image(img)
        butt.connect_object("clicked", self.closePage, area)
        top.pack_end(butt, False, False, 0)

        butt.show()
        top.show()

        self.notebook.insert_page(area, top, 0)

        pages = self.notebook.get_n_pages()
        self.notebook.set_current_page(0)

    def openFile(self, *args):
        if (not self.getModified()) or self.ask("There are unsaved files.\nContinue?"):
            fn = gtk.FileChooserDialog(title="Save File",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
            _filter = gtk.FileFilter()
            _filter.set_name("Micro:Pi Files")
            _filter.add_pattern("*.%s" % SETTINGS['fileExtention'])
            fn.add_filter(_filter)
            _filter = gtk.FileFilter()
            _filter.set_name("All Files")
            _filter.add_pattern("*")
            fn.add_filter(_filter)
            fn.show()

            resp = fn.run()
            if resp == gtk.RESPONSE_OK:
                try:
                    #text = open(fn.get_filename()).read()
                    #try:
                        #d = text.replace("\n", "")
                        #d = base64.b64decode(d)
                        #data = pickle.loads(d)
                    #except:
                        #data = pickle.loads(text)
                    data = self.loadFilesFromFile(fn.get_filename())

                    mw = MainWin(data)
                    yes = True
                    mw.saveLocation = fn.get_filename()
                    mw.setSaved()
                    OPENWINDOWS.append(mw)
                except Exception as e:
                    yes = False
            fn.destroy()
            if resp == gtk.RESPONSE_OK and not yes:
                self.message("File is not a Micro:Pi File")

    def forceOpenFileByFN(self, fn, *args):
        yes = True
        try:
            data = self.loadFilesFromFile(fn)

            sys.argv = [sys.argv[0]]
            mw = MainWin(data)
            mw.saveLocation = fn
            mw.setSaved()
            OPENWINDOWS.append(mw)
            self.destroy()
            yes = True
        except Exception as e:
            yes = False
        if not yes:
            self.message("File is not a Micro:Pi File")

    def save(self, *args):
        self.saveInternalOpenFiles()

        if self.saveLocation:

            _dir = tempfile.mkdtemp()

            def f(d, p):
                for i, j in d.items():
                    if j[0]:
                        open(os.path.join(p, i), "w").write(j[1])
                    else:
                        os.mkdir(os.path.join(p, i))
                        f(j[1], os.path.join(p, i))
            f(self.files, _dir)

            with tarfile.open(self.saveLocation + ".tar.gz", "w:gz") as tar:
                for i in os.listdir(_dir):
                    p = os.path.join(_dir, i)
                    tar.add(p, arcname=os.path.basename(p))

            shutil.rmtree(_dir)
            os.rename(self.saveLocation + ".tar.gz", self.saveLocation)

            self.setSaved()
        else:
            self.saveAs()

    def onTreeviewButtonPressEvent(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo



                model = self.treeView.get_model()

                _iter = model.get_iter(path)
                filename = model.get_value(_iter, 1)
                isFile = model.get_value(_iter, 2)

                listP = []
                p = path
                while p:
                    _iter = model.get_iter(p)
                    fn = model.get_value(_iter, 1)
                    p = p[:-1]
                    listP = [fn] + listP

                self.tvMenuOn = listP

                treeview.grab_focus()
                treeview.set_cursor(path, col, 0)

                if isFile:
                    self.filepopup.popup(None, None, None, event.button, time)
                else:
                    self.dirpopup.popup(None, None, None, event.button, time)
            else:
                self.outpopup.popup(None, None, None, event.button, time)
            return True

    def saveAs(self, *args):
        self.saveInternalOpenFiles()

        fn = gtk.FileChooserDialog(title="Save File As",
                                   action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                   buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        _filter = gtk.FileFilter()
        _filter.set_name("Micro:Pi Files")
        _filter.add_pattern("*.%s" % SETTINGS['fileExtention'])
        fn.add_filter(_filter)
        _filter = gtk.FileFilter()
        _filter.set_name("All Files")
        _filter.add_pattern("*")
        fn.add_filter(_filter)
        fn.show()

        resp = fn.run()

        #files = []
        #for f in self.notebook:
            #fin = self.notebook.get_tab_label(f).get_children()[0].get_label()
            #tb = f.get_child().get_buffer()
            #txt = tb.get_text(*tb.get_bounds())
            #files.append([fin, txt])
        #data = base64.b64encode(pickle.dumps(files))
        #data = "".join(data[i:i+64]+"\n" for i in xrange(0, len(data), 64))

        if resp == gtk.RESPONSE_OK:
            fp = fn.get_filename()
            if fp[-(len(SETTINGS["fileExtention"])+1):] != "." + SETTINGS["fileExtention"]:
                fp += "." + SETTINGS["fileExtention"]
            #open(fp, 'w').write(data)
            self.saveLocation = fp
            self.save()
            self.setSaved()
        fn.destroy()

    def destroy(self, *args):
        if (not self.getModified()) or self.ask("There are unsaved files.\nContinue?"):
            self.active = False
            self.window.hide()
            kill = True
            for i in OPENWINDOWS:
                if i.active:
                    kill = False
            OPENWINDOWS.remove(self)
            if kill:
                gtk.main_quit()
            return False
        return True

    def message(self, message):
        dia = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, message)
        dia.show()
        dia.run()
        dia.destroy()
        return False

    def ask(self, query):
        dia = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, query)
        dia.show()
        rtn=dia.run()
        dia.destroy()
        return rtn == gtk.RESPONSE_YES

    def askQ(self, query, prompt=None, title="", ok="Ok"):
        if prompt:
            dia = EntryDialog(title, self.window, gtk.DIALOG_DESTROY_WITH_PARENT, (ok, gtk.RESPONSE_OK, "Cancel", gtk.RESPONSE_CANCEL), query, default_value=prompt)
        else:
            dia = EntryDialog(title, self.window, gtk.DIALOG_DESTROY_WITH_PARENT, (ok, gtk.RESPONSE_OK, "Cancel", gtk.RESPONSE_CANCEL), query)
        dia.show()
        rtn=dia.run()
        dia.destroy()
        return rtn

    def loadExample(self, example):
        if os.path.exists(os.path.join(WORKINGDIR, example)):
            #if (not self.getModified()) or self.ask("There are unsaved files.\nContinue?"):
            text = open(example).read()
            try:
                try:
                    data = pickle.loads(base64.b64decode(text.replace("\n", "")))
                except Exception as e:
                    data = pickle.loads(text)

                mw = MainWin(data)
                yes = True
                mw.saveLocation = ''
                mw.setSaved()
                OPENWINDOWS.append(mw)
            except:
                yes = False

    def newProject(self, *args):
        #if (not self.getModified()) or self.ask("There are unsaved files.\nContinue?"):
        mw = MainWin()
        mw.saveLocation = ''
        mw.setSaved()
        OPENWINDOWS.append(mw)

    def clearBuild(self):
        if os.path.exists(os.path.join(buildLocation, "source/")):
            for i in os.listdir(os.path.join(buildLocation, "source/")):
                os.remove(os.path.join(buildLocation, "source/", i))
        delFolder(os.path.join(buildLocation,
                               "build/bbc-microbit-classic-gcc/source/"))

    def startBuild(self, *args):

        self.saveInternalOpenFiles()

        global mbedUploading
        global mbedBuilding
        global uBitUploading
        global uBitFound
        global pipes
        if not (mbedUploading or mbedBuilding):
            for w in OPENWINDOWS:
                txtB = gtkSourceView.Buffer()
                txtB.set_style_scheme(self.style_scheme)
                txtB.set_highlight_matching_brackets(False)
                txtB.set_highlight_syntax(False)
                txtB.place_cursor(txtB.get_start_iter())

                w.consoleBody.props.buffer = txtB
            mbedBuilding = True
            self.clearBuild()

            def f(d, p):
                for i, j in d.items():
                    if j[0]:
                        open(os.path.join(p, i), "w").write(j[1])
                    else:
                        os.mkdir(os.path.join(p, i))
                        f(j[1], os.path.join(p, i))
            f(self.files, os.path.join(buildLocation, "source/"))

            os.chdir(buildLocation)
            os.environ["PWD"] = buildLocation

            if WINDOWS:
                p = Popen(
                    "cd %s & yotta --plain build" % buildLocation,
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE
                )
            else:
                p = Popen(
                    ["cd %s; yotta --plain build" % buildLocation],
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE,
                    close_fds = True
                )
            pipes = [p.stdin, NBSR(p.stdout, p), NBSR(p.stderr, p)]

    def startBuildAndUpload(self, *args):
        global mbedUploading
        global mbedBuilding
        global uBitUploading
        global uBitFound
        global pipes

        self.saveInternalOpenFiles()

        if not (mbedUploading or mbedBuilding):
            txtB = gtkSourceView.Buffer()
            txtB.set_style_scheme(self.style_scheme)
            txtB.set_highlight_matching_brackets(False)
            txtB.set_highlight_syntax(False)
            txtB.place_cursor(txtB.get_start_iter())

            self.consoleBody.props.buffer = txtB
            mbedBuilding = True
            mbedUploading = True
            self.clearBuild()


            def f(d, p):
                for i, j in d.items():
                    if j[0]:
                        open(os.path.join(p, i), "w").write(j[1])
                    else:
                        os.mkdir(os.path.join(p, i))
                        f(j[1], os.path.join(p, i))
            f(self.files, os.path.join(buildLocation, "source/"))

            os.chdir(buildLocation)
            os.environ["PWD"] = buildLocation

            if WINDOWS:
                p = Popen(
                    "cd %s & yotta --plain build" % buildLocation,
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE
                )
            else:
                p = Popen(
                    ["cd %s; yotta --plain build" % buildLocation],
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE,
                    close_fds = True
                )
            pipes = [p.stdin, NBSR(p.stdout, p), NBSR(p.stderr, p)]

    def importFile(self, *args):
        fn = gtk.FileChooserDialog(title="Import File",
                                   action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                   buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        _filter = gtk.FileFilter()
        _filter.set_name("C++ Files")
        _filter.add_pattern("*.cpp")
        _filter.add_pattern("*.h")
        fn.add_filter(_filter)
        _filter = gtk.FileFilter()
        _filter.set_name("All Files")
        _filter.add_pattern("*")
        fn.add_filter(_filter)
        fn.show()

        resp = fn.run()
        if resp == gtk.RESPONSE_OK:
            text = open(fn.get_filename()).read()

            self.addNotebookPage(os.path.basename(fn.get_filename()), text)

        fn.destroy()

    def forceUpload(self, *args):
        global mbedUploading
        global mbedBuilding
        global uBitUploading
        global uBitFound
        global pipes
        if os.path.exists("%s/build/bbc-microbit-classic-gcc/source/microbit-build-combined.hex" % buildLocation):
            if (not mbedBuilding) and (not mbedUploading):
                uBitUploading = True
                thread = Thread(target=upload, args=(self,))
                thread.daemon = True
                thread.start()

    def closePage(self, widget, *args):
        self.saveInternalOpenFiles()

        if self.getModified():
            self.modified = True

        pn = self.notebook.page_num(widget)
        fn = self.notebook.get_tab_label(widget).get_tooltip_text()
        self.openFiles.remove(fn)
        self.notebook.remove_page(pn)

    def newPage(self, *args):
        pageName = self.askQ("File Name")
        if pageName:
            self.addNotebookPage(pageName, '')

    def getModified(self):
        return any([self.modified] + [i.get_child().get_buffer().get_modified() for i in self.notebook])

    def setSaved(self):
        for i in self.notebook:
            i.get_child().props.buffer.set_modified(False)
        self.modified = True

    def showSettings(self, *args):
        sd=SettingsDialog()
        sd.run()
        sd.destroy()

    def main(self):
        thread = Thread(target=uBitPoller)
        thread.daemon = True
        thread.start()
        thread = Thread(target=pipePoller, args=(self,))
        thread.daemon = True
        thread.start()
        thread = Thread(target=updateTitle)
        thread.daemon = True
        thread.start()
        gtk.main()




    def send(self, *args):
        if self.serialConnection:
            self.serialConnection.write(self.entry.get_text() + '\n')
        self.entry.set_text('')

    def clear(self, *args):
        txtB = gtkSourceView.Buffer()
        txtB.set_style_scheme(self.style_scheme)
        txtB.set_highlight_matching_brackets(False)
        txtB.set_highlight_syntax(False)
        txtB.place_cursor(txtB.get_start_iter())
        self.consoleBody.set_buffer(txtB)

    def refresh(self, *args):
        self.ports = list(list_ports.grep(''))
        #self.serialLocation = self.ports[0][0] if self.ports else None
        #self.serialConnection = None if not self.serialLocation else serial.serial_for_url(self.serialLocation)
        #if self.serialLocation is not None:
            #self.serialConnection.baudrate = self.baudrate
        self.gtkserialloc.get_model().clear()
        for i in self.ports:
            self.gtkserialloc.append_text(i[0])
        self.gtkserialloc.set_active(0 if self.ports else -1)

    def brtchange(self, widget, *args):
        model = widget.get_model()
        index = widget.get_active()
        newbdrate = int(model[index][0])
        self.baudrate = newbdrate
        if not self.serialConnection:
            self.serialConnection = serial.serial_for_url(self.serialLocation)
        self.serialConnection.baudrate = newbdrate

    def connectToPort(self, *args):
        self.portchange(self.gtkserialloc)

    def portchange(self, widget, *args):
        model = widget.get_model()
        index = widget.get_active()
        if 0 <= index < len(model):
            newport = model[index][0]
            self.serialLocation = newport
            if not self.serialConnection:
                self.serialConnection = serial.serial_for_url(self.serialLocation)
            self.serialConnection.port = newport
            self.serialConnection.baudrate = self.baudrate


class SerialConsole:
    def __init__(self, indep=False):
        self.indep = indep

        if SENDIMAGE:
            self.imageCreator = ImageCreator()

        self.baudrate = 115200
        self.ports = list(list_ports.grep(''))
        #self.serialLocation = self.ports[0][0] if self.ports else None
        self.serialLocation =  None
        #self.serialConnection = None if not self.serialLocation else serial.serial_for_url(self.serialLocation)
        self.serialConnection = None
        if self.serialLocation is not None:
            self.serialConnection.baudrate = self.baudrate

        thread = Thread(target=serialPoller, args=(self,))
        thread.daemon = True
        thread.start()

        mgr = gtkSourceView.style_scheme_manager_get_default()
        self.style_scheme = mgr.get_scheme("tango" if SETTINGS["theme"]=="light" else "oblivion")

        self.window = gtk.Window()
        self.window.set_title("Serial Monitor")
        self.window.set_icon_from_file(os.path.join(WORKINGDIR, "data", "icon.png"))
        self.window.resize(750, 400)
        colour = gtk.gdk.color_parse(DARKCOL)
        self.window.modify_bg(gtk.STATE_NORMAL, colour)

        self.vbox = gtk.VBox()
        self.vbox.show()

        self.consoleFrame = gtk.ScrolledWindow()
        self.consoleFrame.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_ALWAYS)
        self.consoleFrame.show()

        txtB = gtkSourceView.Buffer()
        txtB.set_style_scheme(self.style_scheme)
        txtB.set_highlight_matching_brackets(False)
        txtB.set_highlight_syntax(False)
        txtB.place_cursor(txtB.get_start_iter())

        self.consoleBody = SourceView(txtB)
        self.consoleBody.modify_font(pango.FontDescription("Monospace 10"))
        self.consoleBody.show()
        self.consoleFrame.add(self.consoleBody)
        self.consoleBody.set_editable(False)
        self.vbox.pack_start(self.consoleFrame, 2)

        self.entryHBox = gtk.HBox()
        self.entry = gtk.Entry()
        self.entryHBox.pack_start(self.entry, True, True, 2)
        self.entry.show()
        self.entry.connect("activate", self.send)
        self.sendButton = gtk.Button("Send")
        self.entryHBox.pack_start(self.sendButton, False, False, 2)
        self.sendButton.show()
        self.sendButton.connect("clicked", self.send)
        if SENDIMAGE:
            self.sendImageButton = gtk.Button("Send Image")
            self.entryHBox.pack_start(self.sendImageButton, False, False, 2)
            self.sendImageButton.show()
            self.sendImageButton.connect("clicked", self.showImageCreator)

        self.entryHBox.show()
        self.vbox.pack_start(self.entryHBox, False, False, 2)

        self.hbox = gtk.HBox()
        self.hbox.show()
        self.gtkbaudrate = gtk.combo_box_new_text()
        self.gtkbaudrate.append_text("300")
        self.gtkbaudrate.append_text("1200")
        self.gtkbaudrate.append_text("2400")
        self.gtkbaudrate.append_text("4800")
        self.gtkbaudrate.append_text("9600")
        self.gtkbaudrate.append_text("19200")
        self.gtkbaudrate.append_text("38400")
        self.gtkbaudrate.append_text("57600")
        self.gtkbaudrate.append_text("115200")
        self.gtkbaudrate.show()
        self.gtkbaudrate.set_active(8)
        self.gtkbaudrate.connect("changed", self.brtchange)
        self.hbox.pack_start(self.gtkbaudrate, False, False)

        self.refreshButton = gtk.Button("Refresh")
        self.refreshButton.show()
        self.refreshButton.connect("clicked", self.refresh)
        self.hbox.pack_start(self.refreshButton, True, False)

        self.clearButton = gtk.Button("Clear")
        self.clearButton.show()
        self.clearButton.connect("clicked", self.clear)
        self.hbox.pack_start(self.clearButton, True, False)

        self.connHBox = gtk.HBox()

        self.gtkserialloc = gtk.combo_box_new_text()
        for i in self.ports:
            self.gtkserialloc.append_text(i[0])
        self.gtkserialloc.show()
        self.gtkserialloc.set_active(0)
        #self.gtkserialloc.connect("changed", self.portchange)
        self.gtkserialloc.show()
        self.hbox.pack_start(self.gtkserialloc, False, False)

        self.connectButton = gtk.Button("Connect")
        self.connectButton.show()
        self.connectButton.connect("clicked", self.connectToPort)
        self.hbox.pack_start(self.connectButton, False, False)

        self.vbox.pack_start(self.hbox, False, False, 0)

        self.window.add(self.vbox)

        self.shown = False

        self.window.connect("delete_event", self.destroy)

    def send(self, *args):
        if self.serialConnection:
            self.serialConnection.write(self.entry.get_text() + '\n')
        self.entry.set_text('')

    def clear(self, *args):
        txtB = gtkSourceView.Buffer()
        txtB.set_style_scheme(self.style_scheme)
        txtB.set_highlight_matching_brackets(False)
        txtB.set_highlight_syntax(False)
        txtB.place_cursor(txtB.get_start_iter())
        self.consoleBody.set_buffer(txtB)

    def refresh(self, *args):
        self.ports = list(list_ports.grep(''))
        #self.serialLocation = self.ports[0][0] if self.ports else None
        #self.serialConnection = None if not self.serialLocation else serial.serial_for_url(self.serialLocation)
        #if self.serialLocation is not None:
            #self.serialConnection.baudrate = self.baudrate
        self.gtkserialloc.get_model().clear()
        for i in self.ports:
            self.gtkserialloc.append_text(i[0])
        self.gtkserialloc.set_active(0 if self.ports else -1)

    def brtchange(self, widget, *args):
        model = widget.get_model()
        index = widget.get_active()
        newbdrate = int(model[index][0])
        self.baudrate = newbdrate
        if not self.serialConnection:
            self.serialConnection = serial.serial_for_url(self.serialLocation)
        self.serialConnection.baudrate = newbdrate

    def connectToPort(self, *args):
        self.portchange(self.gtkserialloc)

    def portchange(self, widget, *args):
        model = widget.get_model()
        index = widget.get_active()
        if 0 <= index < len(model):
            newport = model[index][0]
            self.serialLocation = newport
            if not self.serialConnection:
                self.serialConnection = serial.serial_for_url(self.serialLocation)
            self.serialConnection.port = newport
            self.serialConnection.baudrate = self.baudrate

    def destroy(self, *args):
        if not self.indep:
            self.window.hide()
            self.shown = False
            return True
        else:
            self.window.destroy()
            gtk.main_quit()

    def toggleVis(self, *args):
        if self.shown:
            self.shown = False
            self.window.hide()
        else:
            self.shown = True
            txtB = gtkSourceView.Buffer()
            txtB.set_style_scheme(self.style_scheme)
            txtB.set_highlight_matching_brackets(False)
            txtB.set_highlight_syntax(False)
            txtB.place_cursor(txtB.get_start_iter())
            self.consoleBody.set_buffer(txtB)
            self.window.show()

    def insertImage(self, image, *args):
        if self.serialConnection:
            self.serialConnection.write(image)

    def showImageCreator(self, *args):
        self.imageCreator.show(self.insertImage)

class ImageCreator:

    def __init__(self, *args, **kwargs):
        self.window = gtk.Window()
        self.window.set_title("Create An Image")
        self.window.set_icon_from_file(os.path.join(WORKINGDIR, "data", "icon.png"))
        colour = gtk.gdk.color_parse(DARKCOL)
        self.window.modify_bg(gtk.STATE_NORMAL, colour)

        self.vvbox = gtk.VBox()
        self.table = gtk.Table(5, 5)
        self.table.set_border_width(2)
        self.table.set_row_spacings(2)
        self.table.set_col_spacings(2)
        self.buttons = {}

        for y in range(5):
            for x in range(5):
                eb = gtk.EventBox()
                i = gtk.Image()
                i.set_from_file(os.path.join(WORKINGDIR, "data", "selected.png"))
                i.show()
                eb.add(i)
                eb.hide()
                eb.modify_bg(gtk.STATE_NORMAL, colour)
                eb.connect_object("button-press-event", self.togglePart, (x, y))

                eb2 = gtk.EventBox()
                i2 = gtk.Image()
                i2.set_from_file(os.path.join(WORKINGDIR, "data", "unselected.png"))
                i2.show()
                eb2.add(i2)
                eb2.show()
                eb2.modify_bg(gtk.STATE_NORMAL, colour)
                eb2.connect_object("button-press-event", self.togglePart, (x, y))

                self.buttons[(x, y)] = (eb, eb2)

                self.table.attach(eb, x, x + 1, y, y + 1)
                self.table.attach(eb2, x, x + 1, y, y + 1)

        self.table.show()
        self.vvbox.pack_start(self.table)
        hbox = gtk.HBox()
        self.confirmButton = gtk.Button("Okay")
        self.confirmButton.show()
        self.confirmButton.connect("clicked", self.okay)
        hbox.pack_start(self.confirmButton, True, False)
        cancelButton = gtk.Button("Cancel")
        cancelButton.connect("clicked", self.destroy)
        cancelButton.show()
        hbox.pack_end(cancelButton, True, False)
        hbox.show()
        self.vvbox.pack_start(hbox)
        self.vvbox.show()
        self.window.add(self.vvbox)
        self.onOkay = None

        self.running = True
        self.destoryed = False

    def destroy(self, *args):
        self.window.hide()

    def okay(self, *args):
        data = ''
        self.window.hide()
        for y in range(5):
            line = []
            for x in range(5):
                line.append(str(int(self.buttons[(x, y)][0].props.visible)))
            data += ','.join(line) + '\n'
        data += ";"

        if self.onOkay:
            self.onOkay(data)

    def show(self, onOkay, *args):
        for i in self.buttons:
            self.buttons[i][1].show()
            self.buttons[i][0].hide()
        self.onOkay = onOkay
        self.window.show()

    def hide(self, *args):
        self.window.hide()

    def togglePart(self, pos, *args):
        if self.buttons[pos][0].props.visible:
            self.buttons[pos][0].hide()
            self.buttons[pos][1].show()
        else:
            self.buttons[pos][1].hide()
            self.buttons[pos][0].show()

class FullscreenToggler(object):
    def __init__(self, window, keysym=gtk.keysyms.F11):
        self.window = window
        self.keysym = keysym
        self.window_is_fullscreen = False
        self.window.connect_object("window-state-event", FullscreenToggler.on_window_state_change, self)
    def on_window_state_change(self, event):
        self.window_is_fullscreen = bool(gtk.gdk.WINDOW_STATE_FULLSCREEN & event.new_window_state)
    def toggle(self, event):
        if event.keyval == self.keysym:
            if self.window_is_fullscreen:
                self.window.unfullscreen()
            else:
                self.window.fullscreen()

class SplashScreen:
    def __init__(self):
        imageLoc = random.choice(os.listdir(os.path.join(WORKINGDIR, "data", "splashScreens")))
        imageSize = self.get_image_size(open(os.path.join(WORKINGDIR, "data", "splashScreens", imageLoc), 'rb').read())

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_decorated(False)
        self.window.set_title("Micro:Pi")
        self.window.set_icon_from_file(os.path.join(WORKINGDIR, "data", "icon.png"))
        self.window.set_size_request(imageSize[0], -1)
        self.window.set_position(gtk.WIN_POS_CENTER)
        main_vbox = gtk.VBox(False, 1)
        self.window.add(main_vbox)
        hbox = gtk.HBox(False, 0)
        self.img = gtk.Image()
        self.img.set_from_file(os.path.join(WORKINGDIR, "data", "splashScreens", imageLoc))
        main_vbox.pack_start(self.img, True, True)
        self.lbl = gtk.Label('')
        font = pango.FontDescription("Monospace 7")
        self.lbl.modify_font(font)
        main_vbox.pack_end(self.lbl, False, False)
        self.refresh()
        self.window.show_all()
        self.refresh()
    def get_image_size(self, data):
        def is_png(data):
            return (data[:8] == "\211PNG\r\n\032\n" and (data[12:16] == "IHDR"))
        if is_png(data):
            w, h = struct.unpack(">LL", data[16:24])
            width = int(w)
            height = int(h)
            return width, height
        return -1, -1
    def set_text(self, text):
        self.lbl.props.label = text
        self.refresh()
    def refresh(self):
        while gtk.events_pending():
            gtk.main_iteration()

class SettingsDialog(gtk.Dialog):

    def __init__(self, parent=None):

        kwargs = {"parent":parent, "flags":gtk.DIALOG_DESTROY_WITH_PARENT|gtk.DIALOG_MODAL, "title":"Preferences", "buttons":(gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)}

        super(SettingsDialog, self).__init__(**kwargs)

        self.set_skip_taskbar_hint(True)

        vb = gtk.VBox()

        tb = gtk.Table(2, 3)
        tb.set_row_spacings(10)

        #hb1 = gtk.HBox()
        l1 = gtk.Label("BBC Micro:Bit Location")
        #hb1.pack_start(l1, True, False)
        self.fcb1 = gtk.FileChooserButton(title="Set BBC Micro:Bit Location")
        self.fcb1.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        self.fcb1.set_filename(SETTINGS["mbitLocation"])
        #hb1.pack_end(fcb1, True, True)

        tb.attach(l1, 0, 1, 0, 1)
        tb.attach(self.fcb1, 1, 2, 0, 1)
        #vb.pack_start(hb1, True, False)

        #hb1 = gtk.HBox()
        l2 = gtk.Label("Quickstart")
        #hb1.pack_start(l1, True, False)
        self.s1 = gtk.CheckButton()
        if SETTINGS["quickstart"]: self.s1.set_active(True)
        #hb1.pack_end(s1, True, True)
        #vb.pack_start(hb1, True, False)

        tb.attach(l2, 0, 1, 1, 2)
        tb.attach(self.s1, 1, 2, 1, 2)

        #hb1 = gtk.HBox()
        l3 = gtk.Label("Theme")
        #hb1.pack_start(l1, True, False)

        vb2 = gtk.VBox()
        rb1 = gtk.RadioButton(None, "Light")
        vb2.pack_start(rb1)
        self.rb2 = gtk.RadioButton(rb1, "Dark")
        vb2.pack_start(self.rb2)
        if SETTINGS["theme"] == "dark": self.rb2.set_active(True)

        #hb1.pack_end(vb2, True, True)

        tb.attach(l3, 0, 1, 2, 3)
        tb.attach(vb2, 1, 2, 2, 3)
        #vb.pack_start(hb1, True, False)

        #entry = gtk.Entry()
        #entry.set_text(str(default_value))
        #entry.connect("activate",
                      #lambda ent, dlg, resp: dlg.response(resp),
                      #self, gtk.RESPONSE_OK)

        #self.vbox.pack_end(entry, True, True, 0)
        self.vbox.pack_end(tb, True, True, 0)

        self.vbox.show_all()

    def set_value(self, text):
        self.entry.set_text(text)

    def run(self):
        result = super(SettingsDialog, self).run()
        if result == gtk.RESPONSE_OK:
            SETTINGS["quickstart"] = self.s1.get_active()
            SETTINGS["theme"] = "dark" if self.rb2.get_active() else "light"
            SETTINGS["mbitLocation"] = self.fcb1.get_filename() if self.fcb1.get_filename() else SETTINGS["mbitLocation"]
            saveSettings()

            if SETTINGS['theme'] == 'dark':
                colour = gtk.gdk.color_parse(DARKCOL)
            else:
                colour = gtk.gdk.color_parse(LIGHTCOL)

            for w in OPENWINDOWS:
                w.window.modify_bg(gtk.STATE_NORMAL, colour)

                mgr = gtkSourceView.style_scheme_manager_get_default()
                w.style_scheme = mgr.get_scheme('tango' if SETTINGS['theme']=='light' else 'oblivion')
                for f in w.notebook:
                    f.get_child().props.buffer.set_style_scheme(w.style_scheme)
                w.serialConsole.window.modify_bg(gtk.STATE_NORMAL, colour)
                if SENDIMAGE: w.serialConsole.imageCreator.window.modify_bg(gtk.STATE_NORMAL, colour)
                w.serialConsole.consoleBody.props.buffer.set_style_scheme(w.style_scheme)
                w.consoleBody.props.buffer.set_style_scheme(w.style_scheme)

        self.destroy()

def main(start="mainwin"):
    global SETTINGS
    global configLocation
    global buildLocation
    global HOMEDIR
    global MICROPIDIR
    global WINDOWS
    global SAVEDIR

    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    ss = SplashScreen()

    ss.set_text('')
    time.sleep(0.2)
    ss.refresh()

    try:
        HOMEDIR = os.path.expanduser('~')
        MICROPIDIR = os.path.join(HOMEDIR, ".micropi")

        FIRSTRUN = False

        TABSIZE = 4

        WINDOWS = os.name == 'nt'

        def copyDir(path, newPath):
            os.mkdir(newPath)
            for i in os.listdir(path):
                sys.stdout.write(os.path.join(path, i) + '\n')
                if os.path.isdir(os.path.join(path, i)):
                    copyDir(os.path.join(path, i), os.path.join(newPath, i))
                else:
                    d = open(os.path.join(path, i)).read()
                    open(os.path.join(newPath, i), 'w').write(d)

        if not os.path.exists(MICROPIDIR):
            os.mkdir(MICROPIDIR)

        defualtConfig = """{
    "fileExtention": "mpi",
    "mbitLocation": "%s",
    "quickstart": %s,
    "theme": "dark"
}"""
        if not os.path.exists(os.path.join(MICROPIDIR, 'config.json')):
            #res = ask("Enable Quick Start?")
            res = True
            res2 = askFolder("Micro:Bit Location")
            if res2 is None:
                message("No location specified!\nUsing /media/MICROBIT")
                res2 = "/media/MICROBIT"
            ss.set_text("Creating Config")
            print("Creating Config")

            open(os.path.join(MICROPIDIR, 'config.json'),
                 'w').write(defualtConfig % (res2, str(res).lower()))
        configLocation = os.path.join(MICROPIDIR, 'config.json')

        if not os.path.exists(os.path.join(HOMEDIR, 'Documents')):
            os.mkdir(os.path.join(HOMEDIR, 'Documents'))
        if not os.path.exists(os.path.join(HOMEDIR, 'Documents', 'MicroPi Projects')):
            os.mkdir(os.path.join(HOMEDIR, 'Documents', 'MicroPi Projects'))
        SAVEDIR = os.path.join(HOMEDIR, 'Documents', 'MicroPi Projects')

        if not os.path.exists(os.path.join(MICROPIDIR, 'buildEnv')):
            FIRSTRUN = True
            ss.set_text("Installing Build Enviroment")
            print("Installing Build Enviroment")

            setupBEnv()
            #f = tempfile.mktemp()
            #open(f, 'wb').write(base64.b64decode(buildenv.benv.replace('\n', '')))
            #tf = tarfile.open(f, 'r:gz')
            #tf.extractall(MICROPIDIR)
            #os.remove(f)
        if os.path.exists(os.path.join(MICROPIDIR, "micropi-build")):
            delFolder(os.path.join(MICROPIDIR, "micropi-build"))

        buildLocation = os.path.join(MICROPIDIR, 'buildEnv')

        SETTINGS = loadSettings()

        def rstbuild():
            delFolder(os.path.join(buildLocation, 'build'))

        if not SETTINGS['quickstart'] or FIRSTRUN:
            rstbuild()
        prevLoc = os.getcwd()
        os.chdir(buildLocation)
        #os.system('cd %s; yotta target bbc-microbit-classic-gcc' % buildLocation)
        if not SETTINGS['quickstart'] or FIRSTRUN:
            _file = """#include "MicroBit.h"

MicroBit uBit;

    int main()
    {
    while (1)
    {
        uBit.sleep(100);
    }
    }
    """

            open('source/main.cpp', 'w').write(_file)
            if WINDOWS:
                p = Popen(
                    'cd %s & yotta --plain build' % buildLocation,
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE
                )
            else:
                p = Popen(
                    ['cd %s; yotta --plain build' % buildLocation],
                    shell=True,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE,
                    close_fds = True
                )
            pipes = [p.stdin, NBSR(p.stdout, p), NBSR(p.stderr, p)]

            while pipes:
                try:
                    d1 = pipes[1].readline()
                    d2 = pipes[2].readline()
                except UnexpectedEndOfStream:
                    pass

                if type(d1) != str:
                    d1 = str(d1, encoding="utf-8")
                if type(d2) != str:
                    d2 = str(d2, encoding="utf-8")

                if d1:
                    ss.set_text(d1[:-1])
                if d2:
                    ss.set_text(d2[:-1])

                if not (pipes[1].alive()) or (not pipes[2].alive()):
                    pipes = None
        os.chdir(prevLoc)
    except Exception as e:
        import traceback
        print traceback.print_exc()
        sys.exit(1)


    if start == "mainwin":
        main = MainWin()
        OPENWINDOWS.append(main)
        ss.window.destroy()
        main.main()
    elif start == "serialc":
        main = SerialConsole(True)
        ss.window.destroy()
        main.window.show()
        gtk.main()

if __name__ == "__main__":
    main()
