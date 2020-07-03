#
# MUSIC𝄞NTWRK
#
# A python library for pitch class set and rhythmic sequences classification and manipulation,
# the generation of networks in generalized music and sound spaces, and the sonification of arbitrary data
#
# Copyright (C) 2018 Marco Buongiorno Nardelli
# http://www.materialssoundmusic.com, mbn@unt.edu
#
# This file is distributed under the terms of the
# GNU General Public License. See the file `License'
# in the root directory of the present distribution,
# or http://www.gnu.org/copyleft/gpl.txt .
#

import time,re,os
import numpy as np
import fractions as fr
import pandas as pd

from ..musicntwrk import RHYTHMSeq
from ..utils.floatize import floatize
from ..utils.rhythmDistance import rhythmDistance

def rLeadNetwork(dictionary,thup,thdw,distance,prob,write):
        
    '''
    •	generation of the network of all minimal rhythm leadings in a generalized musical space of Nc-dim rhythmic cells – based on the rhythm distance operator
    •	input_csv (str)– file containing the dictionary generated by rhythmNetwork
    •	thup, thdw (float)– upper and lower thresholds for edge creation
    •	w (logical) – if True it writes the nodes.csv and edges.csv files in csv format
    •	returns nodes and edges tables as pandas DataFrames
    '''

    start=time.time()    
    # Create network of minimal rhythm leadings from the rhythmDictionary
    
    df = np.asarray(dictionary)

    # write csv for nodes
    dnodes = pd.DataFrame(df[:,0],columns=['Label'])
    if write: dnodes.to_csv('nodes.csv',index=False)
    #dnodes.to_json('nodes.json')
    
    # find edges according to a metric
    N = df[:,1].shape[0]
    dedges = pd.DataFrame(None,columns=['Source','Target','Weight'])
    np.random.seed(int(time.process_time()*10000))
    for i in range(N):
        vector_i = []
        for l in range(len(df[:,1][0].split())):
            vector_i.append(fr.Fraction(df[:,1][i].split()[l]))
        vector_i  = RHYTHMSeq(vector_i)
        for j in range(i,N):
            vector_j = []
            for l in range(len(df[:,1][0].split())):
                vector_j.append(fr.Fraction(df[:,1][j].split()[l]))
            vector_j  = RHYTHMSeq(vector_j)
            pair = floatize(rhythmDistance(vector_i,vector_j,distance))
            if pair < thup and pair > thdw:
                if prob == 1:
                    tmp = pd.DataFrame([[str(i),str(j),str(pair)]],columns=['Source','Target','Weight'])
                    dedges = dedges.append(tmp)
                else:
                    r = np.random.rand()
                    if r <= prob:
                        tmp = pd.DataFrame([[str(i),str(j),str(pair)]],columns=['Source','Target','Weight'])
                        dedges = dedges.append(tmp)
                    else:
                        pass

    # write csv for edges
    if write: dedges.to_csv('edges.csv',index=False)

    return(dnodes,dedges)
