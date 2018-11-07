#
# PCSetPy
#
# A python library for pitch class set classification and manipulation
#
# Copyright (C) 2018 Marco Buongiorno Nardelli
# http://www.sonifipy.com, http://www.materialssoundmusic.com, mbn@unt.edu
#
# This file is distributed under the terms of the
# GNU General Public License. See the file `License'
# in the root directory of the present distribution,
# or http://www.gnu.org/copyleft/gpl.txt .
#

import numpy as np

class PCSet:

    def __init__(self,pcs,T=0,TET=12):
        self.pcs = pcs
        self.TET = TET
        self.T = T

    def normalOrder(self):

        # 1. eliminate duplicates - ascending order
        self.pcs = np.unique(self.pcs)

        # trivial sets
        if len(self.pcs) == 1:
            return(self.pcs-self.pcs[0])
        if len(self.pcs) == 2:
            return(self.pcs)

        # 2. cycle to find the most compact ascending order
        nroll = np.linspace(0,len(self.pcs)-1,len(self.pcs),dtype=int)
        dist = np.zeros((len(self.pcs)),dtype=int)
        for i in range(len(self.pcs)):
            dist[i] = (np.roll(self.pcs,i)[len(self.pcs)-1] - np.roll(self.pcs,i)[0])%self.TET

        # 3. check for multiple compact orders
        for l in range(1,len(self.pcs)):
            if np.array(np.where(dist == dist.min())).shape[1] != 1:
                indx = np.array(np.where(dist == dist.min()))[0]
                nroll = nroll[indx]
                dist = np.zeros((len(nroll)),dtype=int)
                i = 0
                for n in nroll:
                    dist[i] = (np.roll(self.pcs,n)[len(self.pcs)-(1+l)] - np.roll(self.pcs,n)[0])%self.TET
                    i += 1
            else:
                indx = np.array(np.where(dist == dist.min()))[0]
                nroll = nroll[int(indx[0])]
                pcs_norm = np.roll(self.pcs,nroll)
                break
        if np.array(np.where(dist == dist.min())).shape[1] != 1: pcs_norm = self.pcs
        return(pcs_norm)

    def transpose(self):
        return((self.pcs+self.T)%self.TET)

    def inverse(self):
        return(-self.pcs%self.TET)

    def primeForm(self):
        s_orig = self.pcs
        sn = np.sum((self.normalOrder()-self.normalOrder()[0])%self.TET)
        self.pcs = self.inverse()
        si = np.sum((self.normalOrder()-self.normalOrder()[0])%self.TET)
        if sn <= si:
            self.pcs = s_orig
            return((self.normalOrder()-self.normalOrder()[0])%self.TET)
        else:
            return((self.normalOrder()-self.normalOrder()[0])%self.TET)
        self.pcs = s_orig

    def intervalVector(self):
        npc = int((len(self.pcs)**2-len(self.pcs))/2)
        itv = np.zeros(npc,dtype=int)
        n= 0
        for i in range(len(self.pcs)):
            for j in range(i+1,len(self.pcs)):
                if np.abs(self.pcs[i]-self.pcs[j]) > self.TET/2:
                    itv[n] = self.TET-np.abs(self.pcs[i]-self.pcs[j])
                else:
                    itv[n] = np.abs(self.pcs[i]-self.pcs[j])
                n += 1
        bins = np.linspace(1,self.TET/2+1,self.TET/2+1,dtype=int)
        return(np.histogram(itv,bins)[0])

    def forteClass(self):
        if self.TET != 12:
            print('Forte class defined only for 12-TET')
            return()
        forteDict = {'[012]':'[3-1]','[013]':'[3-2]','[014]':'[3-3]','[015]':'[3-4]','[016]':'[3-5]',
        '[024]':'[3-6]','[025]':'[3-7]','[026]':'[3-8]','[027]':'[3-9]','[036]':'[3-10]',
        '[037]':'[3-11]','[048]':'[3-12]','[0123]':'[4-1]','[0124]':'[4-2]','[0125]':'[4-4]',
        '[0126]':'[4-5]','[0127]':'[4-6]','[0134]':'[4-3]','[0135]':'[4-11]','[0136]':'[4-13]',
        '[0137]':'[4-Z29]','[0145]':'[4-7]','[0146]':'[4-Z15]','[0147]':'[4-18]','[0148]':'[4-19]',
        '[0156]':'[4-8]','[0157]':'[4-16]','[0158]':'[4-20]','[0167]':'[4-9]','[0235]':'[4-10]',
        '[0236]':'[4-12]','[0237]':'[4-14]','[0246]':'[4-21]','[0247]':'[4-22]','[0248]':'[4-24]',
        '[0257]':'[4-23]','[0258]':'[4-27]','[0268]':'[4-25]','[0347]':'[4-17]','[0358]':'[4-26]',
        '[0369]':'[4-28]','[01234]':'[5-1]','[01235]':'[5-2]','[01236]':'[5-4]','[01237]':'[5-5]',
        '[01245]':'[5-3]','[01246]':'[5-9]','[01247]':'[5-Z36]','[01248]':'[5-13]','[01256]':'[5-6]',
        '[01257]':'[5-14]','[01258]':'[5-Z38]','[01267]':'[5-7]','[01268]':'[5-15]','[01346]':'[5-10]',
        '[01347]':'[5-16]','[01348]':'[5-Z17]','[01356]':'[5-Z12]','[01357]':'[5-24]',
        '[01358]':'[5-27]','[01367]':'[5-19]','[01368]':'[5-29]','[01369]':'[5-31]','[01457]':'[5-Z18]',
        '[01458]':'[5-21]','[01468]':'[5-30]',
        '[01469]':'[5-32]','[01478]':'[5-22]','[01568]':'[5-20]','[02346]':'[5-8]','[02347]':'[5-11]',
        '[02357]':'[5-23]','[02358]':'[5-25]','[02368]':'[5-28]','[02458]':'[5-26]','[02468]':'[5-33]',
        '[02469]':'[5-34]','[02479]':'[5-35]','[03458]':'[5-Z37]','[012345]':'[6-1]','[012346]':'[6-2]',
        '[012347]':'[6-Z36]','[012348]':'[6-Z37]','[012356]':'[6-Z3]','[012357]':'[6-9]','[012358]':'[6-Z40]',
        '[012367]':'[6-5]','[012368]':'[6-Z41]','[012369]':'[6-Z42]','[012378]':'[6-Z38]','[012456]':'[6-Z4]',
        '[012457]':'[6-Z11]','[012458]':'[6-15]','[012467]':'[6-Z12]','[012468]':'[6-22]','[012469]':'[6-Z46]',
        '[012478]':'[6-Z17]','[012479]':'[6-Z47]','[012567]':'[6-Z6]','[012568]':'[6-Z43]','[012569]':'[6-Z44]',
        '[012578]':'[6-18]','[012579]':'[6-Z48]','[012678]':'[6-7]','[013457]':'[6-Z10]'
        ,'[013458]':'[6-14]','[013467]':'[6-Z13]','[013468]':'[6-Z24]','[013469]':'[6-27]','[013478]':'[6-Z19]',
        '[013479]':'[6-Z49]','[013568]':'[6-Z25]','[013569]':'[6-Z28]','[013578]':'[6-Z26]','[013579]':'[6-34]',
        '[013679]':'[6-30]','[014568]':'[6-16]','[014579]':'[6-31]','[014589]':'[6-20]','[014679]':'[6-Z50]',
        '[023457]':'[6-8]','[023458]':'[6-Z39]','[023468]':'[6-21]','[023469]':'[6-Z45]','[023568]':'[6-Z23]',
        '[023579]':'[6-33]','[023679]':'[6-Z29]','[024579]':'[6-32]','[0123456]':'[7-1]','[0123457]':'[7-2]',
        '[0123458]':'[7-3]','[0123467]':'[7-4]','[0123468]':'[7-9]','[0123469]':'[7-10]','[0123478]':'[7-6]',
        '[0123479]':'[7-Z12]','[0123567]':'[7-5]','[0123568]':'[7-Z36]','[0123569]':'[7-16]',
        '[0123578]':'[7-14]','[0123579]':'[7-24]','[0145679]':'[7-Z18]','[0123678]':'[7-7]','[0123679]':'[7-19]',
        '[0124568]':'[7-13]','[0124569]':'[7-Z17]','[0124578]':'[7-Z38]','[0124579]':'[7-27]','[0124589]':'[7-21]',
        '[0124678]':'[7-15]','[0124679]':'[7-29]','[0124689]':'[7-30]','[01246810]':'[7-33]','[0125679]':'[7-20]',
        '[0125689]':'[7-22]','[0134568]':'[7-11]','[0134578]':'[7-Z37]','[0134579]':'[7-26]','[0134679]':'[7-31]',
        '[0134689]':'[7-32]','[01346810]':'[7-34]','[0135679]':'[7-28]','[01356810]':'[7-35]','[0234568]':'[7-8]',
        '[0234579]':'[7-23]','[0234679]':'[7-25]','[01234567]':'[8-1]','[01234568]':'[8-2]','[01234569]':'[8-3]',
        '[01234578]':'[8-4]','[01234579]':'[8-11]','[01234589]':'[8-7]',
        '[01234678]':'[8-5]','[01234679]':'[8-13]','[01234689]':'[8-Z15]','[012346810]':'[8-21]','[01234789]':'[8-8]',
        '[01235678]':'[8-6]','[01235679]':'[8-Z29]','[01235689]':'[8-18]','[012356810]':'[8-22]',
        '[01235789]':'[8-16]','[012357810]':'[8-23]','[01236789]':'[8-9]','[01245679]':'[8-14]',
        '[01245689]':'[8-19]','[012456810]':'[8-24]','[01245789]':'[8-20]','[012457810]':'[8-27]',
        '[012467810]':'[8-25]','[01345679]':'[8-12]','[01345689]':'[8-17]','[013457810]':'[8-26]',
        '[013467910]':'[8-28]','[02345679]':'[8-10]','[012345678]':'[9-1]','[012345679]':'[9-2]',
        '[012345689]':'[9-3]','[0123456810]':'[9-6]','[012345789]':'[9-4]','[0123457810]':'[9-7]',
        '[012346789]':'[9-5]','[0123467810]':'[9-8]','[0123467910]':'[9-10]','[0123567810]':'[9-9]',
        '[0123567910]':'[9-11]','[0124568910]':'[9-12]','[0123456789]':'[10-1]','[01234567810]':'[10-2]',
        '[01234567910]':'[10-3]','[01234568910]':'[10-4]','[01234578910]':'[10-5]','[01234678910]':'[10-6]',
        '[012345678910]':'[11-1]','[01234567891011]':'[12-1]'}
        try:
            Fname = forteDict[np.array2string(self.primeForm(),separator='').replace(" ","")]
        except:
            print('set not found')
            Fname=None
        return(Fname)
