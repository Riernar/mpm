Pack manager for Minecraft
==========================

Tool that helps managing modpacks for pack developpers, server owner and end users.

Main features are:
- "packmodes" to differentiate client-only mods, or have a lite version of your pack
- Differential modpack update in a single command, from local zip or a webserver, that can be configured to run on modpack startup in your launcher
- Update over ftp, to update in a command your server. And with packmodes, you don't have to worry about client-only files
- Fully compatible with curse

# Installation
This tool requires [python 3.7](https://www.python.org/) or more recent. See the python website for downloading python for your operating system. You might also be interested in Anaconda, miniconda or other distribution of python.

Clone the repository into a local folder, using git. Optionally, you can download the project as a zip file by clicking "Clone or download > Download Zip".

```
$ git clone https://github.com/Riernar/mpm.git
```

Then, navigate to the directory that was created, or to the folder that you extracted. Open a command line (on Windows, MAJ+Right Click > open powershell here), and install the dependencies. They are specified in the file `requirements.txt`, so you can just ask PIP to install them for you:

```
$ pip install -r requirements.txt
```

> **NOTE**
> On windows, you may have to specify where pip comes from, with:
> ```
> $ python -m pip install -r requirements.txt
> ```

# Usage
The tool is mostly a command-line, but there are a few GUIs. The file `mpm.py` at the top of the project is the command line interface and is executable provided you have python. The command is documented with the `--help` (or `-h`) option.

To get help about the command and subcommands, run:
```
$ ./mpm.py -h
```

See also the [Wiki](https://github.com/Riernar/mpm/wiki)