#!/usr/bin/env python2


"""
This file contains a function which reads in an exodus volume mesh containing 1 
or more blocks of materials. This function while then generate mesh based
geometry and sort labels according to volume. A layer of zero thickness elements
are generated around the perimeter of all but the largest volume for use as 
cohesive elements for modeling interface behavior between different materials.

Labeling of individual entities is handled systematically and the processed file
is converted to an ABAQUS ready input script.

The function contained within relies on Cubit v15.3 or later 
(https://cubit.sandia.gov).

Version: 1.0.0

Date: 2018 October 1

Author: David J. Walters
Los Alamos National Laboratory

Copyright 2019. Triad National Security, LLC. All rights reserved.
This program was produced under U.S. Government contract 89233218CNA000001 for Los Alamos
National Laboratory (LANL), which is operated by Triad National Security, LLC for the U.S.
Department of Energy/National Nuclear Security Administration. All rights in the program are
reserved by Triad National Security, LLC, and the U.S. Department of Energy/National Nuclear
Security Administration. The Government is granted for itself and others acting on its behalf a
nonexclusive, paid-up, irrevocable worldwide license in this material to reproduce, prepare
derivative works, distribute copies to the public, perform publicly and display publicly, and to permit
others to do so.

This program is open source under the BSD-3 License.

Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and
the following disclaimer.
2.Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the
distribution.
3.Neither the name of the copyright holder nor the names of its contributors may be used to endorse
or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import sys


def cohgen(exodusIn,fileOutPrefix):
    """
    This function operates within Cubit. It imports an exodus mesh of
    polycrystalline geometry with the void meshed, generates a skin of zero
    thickness cohesive elements surrounding individual crystals, and exports
    a valid ABAQUS mesh.
    """
    # Provide the installation path of Cubit
    sys.path.append('~/Software/Cubit-15.3-Lin64/bin')
    # sys.path.append('/Applications/Cubit-15.3/Cubit.app/Contents/MacOS/')
    import cubit as cb
    # Start cubit
    cb.init(['cubit','-nojournal'])

    # Import model while creating geometry
    fileIn = "'" + exodusIn + ".e'"
    print fileIn
    cb.cmd("import mesh geometry %s feature_angle 135.00 merge" % fileIn)

    # Get volumes and separate into blocks
    # Compress volume id's and sort by volume (likely void volume is largest)
    cb.cmd('compress all sort')
    # cb.cmd('label volume id')
    # cb.cmd('label volume name id')

    # Remove pre-established element blocks
    cb.cmd('del block all')
    vols = cb.get_volume_count()
    print "Number of volumes: %s" % vols

    # Check if volumes sorted properly (largest last)
    firstvol = cb.volume(1)
    lastvol = cb.volume(vols)
    firstvol_vol = firstvol.volume()
    lastvol_vol = lastvol.volume()

    # Set volume number containing matrix material
    # Proper sort should set last (assuming it is the largest individual volume)
    # One case, it left the matrix material as volume 1
    # Could be other cases requiring a more generic fix (check cuibt file manually)
    if firstvol_vol > lastvol_vol:
        matrix_vol_num = 1
    elif firstvol_vol < lastvol_vol:
        matrix_vol_num = vols


    # Assign each grain its own element block and name.
    grain_list=[]
    for cv in range(1,vols+1):
        cb.cmd("block %s add volume %s" % (repr(cv+1),repr(cv)))
        if cv == matrix_vol_num:
            cb.cmd("block %s name 'Matrix'" % repr(cv+1))
        else:
            cb.cmd("block %s name 'Grain_%s'" % (repr(cv+1),repr(cv)))
            grain_list.append('Grain_%s' % repr(cv))

    cb.cmd('disassociate mesh from Volume all')
    # cb.cmd('delete volume all')

    # Pillow each grain to skin with 0 thickness hexes for cohesive elements
    el_blocks = cb.get_block_count()
    # Note, indexing skips last element block (presumed binder)
    for block in range(2,el_blocks+1):
        if block == matrix_vol_num+1:
            pass
        else:
            cb.cmd("pillow hex in block %s distance 0 no_smooth" % repr(block))

    cb.cmd('block 1 add hex not block_assigned')
    cb.cmd("block 1 name 'Coh_El'")

    # Get bounding box for removing cohesive elements on the domain boundary
    # cb.get_bounding_box('entity',id) returns a vector with the following info:
    #(min_x, max_x, range_x, min_y, max_y, range_y, min_z, max_z, range_z, diag)
    bbox = cb.get_bounding_box("volume",matrix_vol_num)

    cb.cmd('delete hex in block 1 with X_Coord == %s' % repr(bbox[0]))
    cb.cmd('delete hex in block 1 with X_Coord == %s' % repr(bbox[1]))
    cb.cmd('delete hex in block 1 with Y_Coord == %s' % repr(bbox[3]))
    cb.cmd('delete hex in block 1 with Y_Coord == %s' % repr(bbox[4]))
    cb.cmd('delete hex in block 1 with Z_Coord == %s' % repr(bbox[6]))
    cb.cmd('delete hex in block 1 with Z_Coord == %s' % repr(bbox[7]))

    # Reassign domain nodesets since pillowing and removing domain hexes messes this up
    cb.cmd('delete nodeset all')
    cb.cmd('delete sideset all')

    cb.cmd('nodeset 1 add node with X_Coord == %s' % repr(bbox[0]))
    cb.cmd('nodeset 2 add node with X_Coord == %s' % repr(bbox[1]))
    cb.cmd('nodeset 3 add node with Y_Coord == %s' % repr(bbox[3]))
    cb.cmd('nodeset 4 add node with Y_Coord == %s' % repr(bbox[4]))
    cb.cmd('nodeset 5 add node with Z_Coord == %s' % repr(bbox[6]))
    cb.cmd('nodeset 6 add node with Z_Coord == %s' % repr(bbox[7]))
    cb.cmd('nodeset 7 add node in nodeset 1 to 6')
    cb.cmd('nodeset 8 add node in hex in block 1') # Interface nodes

    cb.cmd('nodeset 1 name "negXNodes"')
    cb.cmd('nodeset 2 name "posXNodes"')
    cb.cmd('nodeset 3 name "negYNodes"')
    cb.cmd('nodeset 4 name "posYNodes"')
    cb.cmd('nodeset 5 name "negZNodes"')
    cb.cmd('nodeset 6 name "posZNodes"')
    cb.cmd('nodeset 7 name "allBoundaryNodes"')
    cb.cmd('nodeset 8 name "matIntNodes"')

    # Define nodesets for periodic boundary conditions. For universal application
    # to implicit and explicit analyses, corners, edges, and faces cannot contain
    # duplicate nodes (restriction for implicit only). Therefore, new specific
    # nodesets are defined in a way to eleminate this duplicate definition problem.

    # Redefine Faces for PBC's
    cb.cmd('nodeset 101 add node in nodeset 1')
    cb.cmd('nodeset 102 add node in nodeset 2')
    cb.cmd('nodeset 103 add node in nodeset 3')
    cb.cmd('nodeset 104 add node in nodeset 4')
    cb.cmd('nodeset 105 add node in nodeset 5')
    cb.cmd('nodeset 106 add node in nodeset 6')

    cb.cmd('nodeset 101 name "PBCnXF"')
    cb.cmd('nodeset 102 name "PBCpXF"')
    cb.cmd('nodeset 103 name "PBCnYF"')
    cb.cmd('nodeset 104 name "PBCpYF"')
    cb.cmd('nodeset 105 name "PBCnZF"')
    cb.cmd('nodeset 106 name "PBCpZF"')

    # Define Edges for PBC's
    cb.cmd('nodeset 1001 add node with X_Coord == {x:s} and with Y_Coord == {y:s}'.format(x=repr(bbox[0]),y=repr(bbox[3])))
    cb.cmd('nodeset 1001 name "PBCnXnYE"')
    cb.cmd('nodeset 1002 add node with X_Coord == {x:s} and with Y_Coord == {y:s}'.format(x=repr(bbox[0]),y=repr(bbox[4])))
    cb.cmd('nodeset 1002 name "PBCnXpYE"')
    cb.cmd('nodeset 1003 add node with X_Coord == {x:s} and with Y_Coord == {y:s}'.format(x=repr(bbox[1]),y=repr(bbox[3])))
    cb.cmd('nodeset 1003 name "PBCpXnYE"')
    cb.cmd('nodeset 1004 add node with X_Coord == {x:s} and with Y_Coord == {y:s}'.format(x=repr(bbox[1]),y=repr(bbox[4])))
    cb.cmd('nodeset 1004 name "PBCpXpYE"')
    cb.cmd('nodeset 1005 add node with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(y=repr(bbox[3]),z=repr(bbox[6])))
    cb.cmd('nodeset 1005 name "PBCnYnZE"')
    cb.cmd('nodeset 1006 add node with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(y=repr(bbox[3]),z=repr(bbox[7])))
    cb.cmd('nodeset 1006 name "PBCnYpZE"')
    cb.cmd('nodeset 1007 add node with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(y=repr(bbox[4]),z=repr(bbox[6])))
    cb.cmd('nodeset 1007 name "PBCpYnZE"')
    cb.cmd('nodeset 1008 add node with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(y=repr(bbox[4]),z=repr(bbox[7])))
    cb.cmd('nodeset 1008 name "PBCpYpZE"')
    cb.cmd('nodeset 1009 add node with X_Coord == {x:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),z=repr(bbox[6])))
    cb.cmd('nodeset 1009 name "PBCnXnZE"')
    cb.cmd('nodeset 1010 add node with X_Coord == {x:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),z=repr(bbox[7])))
    cb.cmd('nodeset 1010 name "PBCnXpZE"')
    cb.cmd('nodeset 1011 add node with X_Coord == {x:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),z=repr(bbox[6])))
    cb.cmd('nodeset 1011 name "PBCpXnZE"')
    cb.cmd('nodeset 1012 add node with X_Coord == {x:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),z=repr(bbox[7])))
    cb.cmd('nodeset 1012 name "PBCpXpZE"')

    # Remove nodes in edge sets from face sets
    for nn in range(101,107):
        cb.cmd('nodeset {num:s} remove node in nodeset 1001 to 1012'.format(num=repr(nn)))

    # Define Corners for PBC's
    cb.cmd('nodeset 10001 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),y=repr(bbox[3]),z=repr(bbox[6])))
    cb.cmd('nodeset 10001 name "PBCnXnYnZC"')
    cb.cmd('nodeset 10002 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),y=repr(bbox[3]),z=repr(bbox[7])))
    cb.cmd('nodeset 10002 name "PBCnXnYpZC"')
    cb.cmd('nodeset 10003 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),y=repr(bbox[4]),z=repr(bbox[6])))
    cb.cmd('nodeset 10003 name "PBCnXpYnZC"')
    cb.cmd('nodeset 10004 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[0]),y=repr(bbox[4]),z=repr(bbox[7])))
    cb.cmd('nodeset 10004 name "PBCnXpYpZC"')
    cb.cmd('nodeset 10005 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),y=repr(bbox[3]),z=repr(bbox[6])))
    cb.cmd('nodeset 10005 name "PBCpXnYnZC"')
    cb.cmd('nodeset 10006 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),y=repr(bbox[3]),z=repr(bbox[7])))
    cb.cmd('nodeset 10006 name "PBCpXnYpZC"')
    cb.cmd('nodeset 10007 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),y=repr(bbox[4]),z=repr(bbox[6])))
    cb.cmd('nodeset 10007 name "PBCpXpYnZC"')
    cb.cmd('nodeset 10008 add node with X_Coord == {x:s} and with Y_Coord == {y:s} and with Z_Coord == {z:s}'.format(x=repr(bbox[1]),y=repr(bbox[4]),z=repr(bbox[7])))
    cb.cmd('nodeset 10008 name "PBCpXpYpZC"')

    # Remove nodes in corner sets from edge sets
    for nn in range(1001,1013):
        cb.cmd('nodeset {num:s} remove node in nodeset 10001 to 10008'.format(num=repr(nn)))


    # Export abaqus file
    absFileOutPrefix = os.path.abspath(fileOutPrefix)
    cb.cmd("set Abaqus precision 4")
    cb.cmd('export abaqus "%s.inp" block all nodeset all dimension 3 overwrite' % absFileOutPrefix)
    cb.cmd('save as "%s.cub" overwrite' % absFileOutPrefix)
    return absFileOutPrefix, grain_list
