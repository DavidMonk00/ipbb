from __future__ import print_function, absolute_import
from future.utils import iterkeys, itervalues, iteritems
# ------------------------------------------------------------------------------

import time
import os
import collections
import copy

from string import Template as tmpl
from ..defaults import kTopEntity
from os.path import abspath, join, split, splitext

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
class VivadoProjectMaker(object):
    """
    Attributes:
        reverse        (bool): flag to invert the file import order in Vivado.
        filesets (obj:`dict`): extension-to-fileset association
    """

    filesets = {
        '.xdc': 'constrs_1',
        '.tcl': 'constrs_1',
        '.mif': 'sources_1',
        '.vhd': 'sources_1',
        '.v': 'sources_1',
        '.sv': 'sources_1',
        '.xci': 'sources_1',
        '.ngc': 'sources_1',
        '.edn': 'sources_1',
        '.edf': 'sources_1',
        '.mem': 'sources_1'
        # Legacy ISE files
        # '.ucf': 'ise_1',
        # '.xco': 'ise_1',
    }

    # --------------------------------------------------------------
    def __init__(self, aProjInfo, aIPCachePath=None, aReverse=False, aTurbo=True):
        self.projInfo = aProjInfo
        self.ipCachePath = aIPCachePath
        self.reverse = aReverse
        self.turbo = aTurbo

    # --------------------------------------------------------------
    def write(self, aTarget, aScriptVariables, aComponentPaths, aCommandList, aLibs):

        lReqVariables = {'device_name', 'device_package', 'device_speed'}
        if not lReqVariables.issubset(aScriptVariables):
            raise RuntimeError("Missing required variables: {}".format(lReqVariables.difference(aScriptVariables)))

        # ----------------------------------------------------------
        write = aTarget

        lWorkingDir = abspath(join(self.projInfo.path, self.projInfo.name))
        lTopEntity = aScriptVariables.get('top_entity', kTopEntity)
        # ----------------------------------------------------------

        write('# Autogenerated project build script')
        write(time.strftime("# %c"))
        write()

        write(
            'create_project {0} {1} -part {device_name}{device_package}{device_speed} -force'.format(
                self.projInfo.name, lWorkingDir, **aScriptVariables
            )
        )

        # Add ip repositories to the project variable
        write('set_property ip_repo_paths {{{}}} [current_project]'.format(
            ' '.join(map( lambda c: c.FilePath, aCommandList['iprepo']))
            )
        )

        write('if {[string equal [get_filesets -quiet constrs_1] ""]} {create_fileset -constrset constrs_1}')
        write('if {[string equal [get_filesets -quiet sources_1] ""]} {create_fileset -srcset sources_1}')

        for setup in (c for c in aCommandList['setup'] if not c.Finalise):
            write('source {0}'.format(setup.FilePath))

        lXciBasenames = []
        # lXciTargetFiles = []

        lSrcs = aCommandList['src'] if not self.reverse else reversed(aCommandList['src'])

        # Grouping commands here, where the order matters only for constraint files
        lSrcCommandGroups = collections.OrderedDict()

        for src in lSrcs:
            # Extract path tokens
            lPath, lBasename = split(src.FilePath)
            lName, lExt = splitext(lBasename)
            # lTargetFile = join(lWorkingDir, aProjInfo.name + '.srcs', 'sources_1', 'ip', lName, lBasename)

            # local list of commands
            lCommands = []

            if lExt == '.xci':

                c = 'import_files -norecurse -fileset sources_1 $files'
                f = src.FilePath

                lCommands += [(c, f)]

                lXciBasenames.append(lName)
                # lXciTargetFiles.append(lTargetFile)
            else:
                if src.Include:

                    c = 'add_files -norecurse -fileset {0} $files'.format(self.filesets[lExt])
                    f = src.FilePath
                    lCommands += [(c, f)]

                    if src.Vhdl2008:
                        c = 'set_property FILE_TYPE {VHDL 2008} [get_files {$files}]'
                        f = src.FilePath
                        lCommands += [(c, f)]
                    if lExt == '.tcl':
                        c = 'set_property USED_IN implementation [get_files {$files}]'
                        f = src.FilePath
                        lCommands += [(c, f)]
                if src.Lib:
                    c = 'set_property library {0} [ get_files {{$files}} ]'.format(src.Lib)
                    f = src.FilePath
                    lCommands += [(c, f)]

            for c, f in lCommands:
                if self.turbo:
                    lSrcCommandGroups.setdefault(c, []).append(f)
                else:
                    write(tmpl(c).substitute(files=f))

        if self.turbo:
            for c, f in iteritems(lSrcCommandGroups):
                write(tmpl(c).substitute(files=' '.join(f)))

        write('set_property top {0} [current_fileset]'.format(lTopEntity))

        write('set_property "steps.synth_design.args.flatten_hierarchy" "none" [get_runs synth_1]')

        if self.ipCachePath:
            write('config_ip_cache -import_from_project -use_cache_location {0}'.format(abspath(self.ipCachePath)))

        for i in lXciBasenames:
            write('upgrade_ip [get_ips {0}]'.format(i))
        # for i in lXciTargetFiles:
            # write('create_ip_run [get_files {0}]'.format(i))
        for i in lXciBasenames:
            write('create_ip_run [get_ips {0}]'.format(i))

        for setup in (c for c in aCommandList['setup'] if c.Finalise):
            write('source {0}'.format(setup.FilePath))


        write('close_project')
    # --------------------------------------------------------------

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
