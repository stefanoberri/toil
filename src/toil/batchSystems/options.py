from __future__ import absolute_import
# Copyright (C) 2015-2016 Regents of the University of California
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
#

from .registry import batchSystemFactoryFor, defaultBatchSystem, uniqueNames

import socket


def getLocalIP():
    # may return localhost on some systems (not osx and coreos) https://stackoverflow.com/a/166520
    return socket.gethostbyname(socket.gethostname())

def _parasolOptions(addOptionFn):
    addOptionFn("--parasolCommand", dest="parasolCommand", default=None,
                      help="The name or path of the parasol program. Will be looked up on PATH "
                           "unless it starts with a slashdefault=%s" % 'parasol')
    addOptionFn("--parasolMaxBatches", dest="parasolMaxBatches", default=None,
                help="Maximum number of job batches the Parasol batch is allowed to create. One "
                     "batch is created for jobs with a a unique set of resource requirements. "
                     "default=%i" % 1000)


def _singleMachineOptions(addOptionFn):
    addOptionFn("--scale", dest="scale", default=None,
                help=("A scaling factor to change the value of all submitted tasks's submitted cores. "
                      "Used in singleMachine batch system. default=%s" % 1))
    addOptionFn("--linkImports", dest="linkImports", default=False, action='store_true',
                help=("When using Toil's importFile function for staging, input files are copied to the job store. "
                      "Specifying this option saves space by hard-linking imported files. As long as caching is "
                      "enabled Toil will protect the file automatically by changing the permissions to read-only."))


def _mesosOptions(addOptionFn):
    addOptionFn("--mesosMaster", dest="mesosMasterAddress", default=None,
                help=("The host and port of the Mesos master separated by colon. default=%s" % 'localhost:5050'))

# Built in batch systems that have options
_OPTIONS = [
    _parasolOptions,
    _singleMachineOptions,
    _mesosOptions
    ]

_options = list(_OPTIONS)


def addOptionsDefinition(optionsDefinition):
    _options.append(optionsDefinition)


def setOptions(config, setOption):
    batchSystem = config.batchSystem

    factory = batchSystemFactoryFor(batchSystem)
    batchSystem = factory()

    batchSystem.setOptions(setOption)


def addOptions(addOptionFn):
    addOptionFn("--batchSystem", dest="batchSystem", default=defaultBatchSystem(),
                help=("The type of batch system to run the job(s) with, currently can be one "
                      "of %s'. default=%s" % (', '.join(uniqueNames()), defaultBatchSystem())))
    addOptionFn("--disableHotDeployment", dest="disableHotDeployment", action='store_true', default=None,
                help=("Should hot-deployment of the user script be deactivated? If True, the user "
                      "script/package should be present at the same location on all workers. "
                      "default=false"))

    for o in _options:
        o(addOptionFn)

def setDefaultOptions(config):
    """
    Set default options for builtin batch systems. This is required if a Config
    object is not constructed from an Options object.
    """
    config.batchSystem = "singleMachine"
    config.disableHotDeployment = False
    config.environment = {}
    config.statePollingWait = 1 # seconds

    # single machine
    config.scale = 1
    config.linkImports = False

    # mesos
    config.mesosMasterAddress = '%s:5050' % getLocalIP()

    # parasol
    config.parasolCommand = 'parasol'
    config.parasolMaxBatches = 10000
