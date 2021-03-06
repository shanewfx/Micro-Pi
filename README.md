[![Build Status](https://travis-ci.org/Bottersnike/Micro-Pi.svg?branch=master)](https://travis-ci.org/Bottersnike/Micro-Pi)
##Summary
Micro:Pi is a pure python IDE (Intergrated
Development Enviroment) designed to run on any system
with python. It has a simple interface and contains a whole
box of tricks such as the serial monitor and image sender/reciver.

##Why use Micro:Pi over alternatives?
Micro:Pi can run entirely offline if you want to. It downloads all
of its dependancys at install time and from that point on no
internet connection is required. Micro:Pi also allows you to program
your BBC Micro:Bit in C++ which is usually only avaliable through
command line interfaces (which Micro:Pi does for you). It also comes
with a built in serial monitor and it's entierly open source.

##Instalation
To install Micro:Pi there is a new script bundled. Open a terminal
in the root folder of Micro:Pi then type `./install.sh`. It has to
be run as root so `sudo sh install.sh` is recommended. Uninstalling
in done by the `uninstall.sh` script and in run in the same way.
If you want to install Micro:Pi without having to download it all first,
download the install.sh file then run
```
sudo sh install.sh --online
```
and it should download and install.

If you are on a non linux system, download this repository from github
then download and install the following:
- python 2.7 [https://www.python.org/.../python-2.7.12.msi](https://www.python.org/ftp/python/2.7.12/python-2.7.12.msi)
- pyGTK2.0 All In One[http://ftp.gnome.org/.../pygtk-all-in-one-2.24.2.win32-py2.7.msi](http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.24/pygtk-all-in-one-2.24.2.win32-py2.7.msi)
    (Be sure to check PyGtkSourceView2 2.10.1 in the installation window)
- yotta [https://mbed-media.mbed.com/.../yotta_install_v023.exe](https://mbed-media.mbed.com/filer_public/2f/0b/2f0b924c-1fac-4907-989b-f2afe3f5785e/yotta_install_v023.exe)
- gcc-arm-none-eabi [https://launchpad.net/.../gcc-arm-none-eabi-4_9-2015q2-20150609-win32.exe](https://launchpad.net/gcc-arm-embedded/4.9/4.9-2015-q2-update/+download/gcc-arm-none-eabi-4_9-2015q2-20150609-win32.exe)

Now you need to add the location where you installed yotta (C:\yotta by
default) and the \bin directory of you gcc-arm-none-eabi installation to
your global path. Instructions for adding to you path can be found at
[http://yottadocs.mbed.com/#windows-path](http://yottadocs.mbed.com/#windows-path).
If you want you can also remove the "Run Yotta" shortcut from your
desktop as you don't need it.

You can then start micropi using
```
cd micropi
python micropi.py
```
An install script for windows is planned by is made hard because windows
doesn't have a package manager.

##Features
- In the top left corner are 4 triangles that indicate the statud of you
    Micro:Bit. It goes green if your Micro:Bit is found, orange if
    it's uploading, and red is if Micro:Pi can't find you Micro:Bit.
- Just underneath the 4 triangles, is your tab view. This allows you to
    create multiple files in your project.
- The large white box in the top half of the screen is your text editor.
    This is where you write your code to put on your Micro:Bit
- Just under that, is where you can find your console. This shows the output
    of the build and upload process. Errors will appear here.
- In the deploy menu, you can find the serial monitor. From here you can
    send and recieve text from your BBC Micro:Bit.

##Contribute
I don't have a PayPal or anything similar but the best way you can contribute
is by just letting people know about Micro:Pi and getting it out.

##Thanks To:
- The MBED team for developing yotta and alot of the build process
- Lancaster University for the microbit-dal runtime that this entire project is built upon
- Joe Finney from Lancaster Uni. for helping me when I was facing problems settings up yotta on my pi
- The entire Raspberry Pi Forums community for answering all my questions


The words "BBC" and "Micro:Bit" and the BBC Micro:Bit logo are all trademarks of the BBC and I lay no claim to them.
