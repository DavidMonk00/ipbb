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
        filesets (obj:`dict`): extension-to-fileset association
    """

    filetypes = {
        'ip' : ('.xci',),
        'constr' : ('.xdc', '.tcl'),
        'design' : ('.vhd', '.vhdl', '.v', '.sv', '.xci', '.ngc', '.edn', '.edf'),
    }

    @staticmethod
    def fileset(aSrcCmd):
        lName, lExt = splitext(aSrcCmd.filepath)

        lFileSet = None
        if lExt in  ('.xci'):
            lFileSet = 'sources_1'

        elif lExt in ('.xdc', '.tcl'):
            lFileSet = 'constrs_1'

        elif lExt in ('.vhd', '.vhdl', '.v', '.sv', '.xci', '.ngc', '.edn', '.edf'):
            if aSrcCmd.useInSynth:
                lFileSet = 'sources_1'
            elif aSrcCmd.useInSim:
                lFileSet = 'sim_1'

        return lFileSet

    # --------------------------------------------------------------
    def __init__(self, aProjInfo, aIPCachePath=None, aTurbo=True):
        self.projInfo = aProjInfo
        self.ipCachePath = aIPCachePath
        self.turbo = aTurbo

    # --------------------------------------------------------------
    def write(self, aOutput, aSettings, aComponentPaths, aCommandList, aLibs):

        lReqVariables = {'device_name', 'device_package', 'device_speed'}
        if not lReqVariables.issubset(aSettings):
            raise RuntimeError("Missing required variables: {}".format(lReqVariables.difference(aSettings)))
        lXilinxPart = "{device_name}{device_package}{device_speed}".format(**aSettings)


        # ----------------------------------------------------------
        write = aOutput

        lWorkingDir = abspath(join(self.projInfo.path, self.projInfo.name))
        lTopEntity = aSettings.get('top_entity', kTopEntity)

        lSimTopEntity = aSettings.get('vivado.sim_top_entity', None)
        # ----------------------------------------------------------

        write('# Autogenerated project build script')
        write(time.strftime("# %c"))
        write()

        write(
            'create_project {0} {1} -part {2} -force'.format(
                self.projInfo.name, lWorkingDir, lXilinxPart
            )
        )

        # Add ip repositories to the project variable
        write('set_property ip_repo_paths {{{}}} [current_project]'.format(
            ' '.join(map( lambda c: c.filepath, aCommandList['iprepo']))
        ))

        for util in (c for c in aCommandList['util']):
            write('add_files -norecurse -fileset utils_1 {0}'.format(util.filepath))

        write('if {[string equal [get_filesets -quiet constrs_1] ""]} {create_fileset -constrset constrs_1}')
        write('if {[string equal [get_filesets -quiet sources_1] ""]} {create_fileset -srcset sources_1}')

        for setup in (c for c in aCommandList['setup'] if not c.finalize):
            write('source {0}'.format(setup.filepath))

        lXciBasenames = []

        lSrcs = aCommandList['src']

        # Grouping commands here, where the order matters only for constraint files
        lSrcCommandGroups = collections.OrderedDict()

        for src in lSrcs:
            #
            # TODO: rationalise the file-type base file handling
            #     Now it's split betweem the following is statement and
            #     the fileset method
            #

            # Extract path tokens
            _, lBasename = split(src.filepath)
            lName, lExt = splitext(lBasename)

            # local list of commands
            lCommands = []

            if lExt == '.xci':

                c = 'import_files -norecurse -fileset {0} $files'.format(self.fileset(src))
                f = src.filepath

                lCommands += [(c, f)]

                lXciBasenames.append(lName)
                # lXciTargetFiles.append(lTargetFile)
            else:

                c = 'add_files -norecurse -fileset {0} $files'.format(self.fileset(src))
                f = src.filepath
                lCommands += [(c, f)]

                if src.vhdl2008:
                    c = 'set_property FILE_TYPE {VHDL 2008} [get_files {$files}]'
                    f = src.filepath
                    lCommands += [(c, f)]

                if lExt == '.tcl':
                    c = 'set_property USED_IN implementation [get_files {$files}]'
                    f = src.filepath
                    lCommands += [(c, f)]
                    
                if src.lib:
                    c = 'set_property library {0} [ get_files {{$files}} ]'.format(src.lib)
                    f = src.filepath
                    lCommands += [(c, f)]

            for c, f in lCommands:
                if self.turbo:
                    lSrcCommandGroups.setdefault(c, []).append(f)
                else:
                    write(tmpl(c).substitute(files=f))

        if self.turbo:
            for c, f in iteritems(lSrcCommandGroups):
                write(tmpl(c).substitute(files=' '.join(f)))

        write('set_property top {0} [sources_1]'.format(lTopEntity))
        if lSimTopEntity:
            write('set_property top {0} [sim_1]'.format(lSimTopEntity))

        if self.ipCachePath:
            write('config_ip_cache -import_from_project -use_cache_location {0}'.format(abspath(self.ipCachePath)))

        for i in lXciBasenames:
            write('upgrade_ip [get_ips {0}]'.format(i))
        # for i in lXciTargetFiles:
            # write('create_ip_run [get_files {0}]'.format(i))
        for i in lXciBasenames:
            write('create_ip_run [get_ips {0}]'.format(i))

        for setup in (c for c in aCommandList['setup'] if c.finalize):
            write('source {0}'.format(setup.filepath))

        write('close_project')
    # --------------------------------------------------------------

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
