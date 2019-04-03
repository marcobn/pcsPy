#
# timbrePy
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

import sys,re,time,os,glob
import numpy as np
from scipy.signal import hilbert
from scipy.signal import argrelextrema
from numpy.linalg import lstsq
import itertools as iter
import pandas as pd
import sklearn.metrics as sklm
import networkx as nx
import community as cm
import music21 as m21
import matplotlib.pyplot as plt
import matplotlib.style as ms
ms.use('seaborn-muted')
#%matplotlib inline
from vpython import *

import librosa
import librosa.display

from bs4 import BeautifulSoup
import urllib
import wget

from mpi4py import MPI

from communications import *
from load_balancing import *

# initialize parallel execution
comm=MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

def orchestralVector(inputfile,barplot=True):
	'''
	build orchestral vector sequence from score
	'''
	score = m21.converter.parse(inputfile)
	score = score.sliceByBeat()
	Nparts = len(score.getElementsByClass(m21.stream.Part))
	orch = init_list_of_objects(Nparts)
	for p in range(Nparts):
		Nmeasures = len(score.getElementsByClass(m21.stream.Part)[p].\
						getElementsByClass(m21.stream.Measure))
		for m in range(0,Nmeasures):
			mea = score.getElementsByClass(m21.stream.Part)[p].\
					getElementsByClass(m21.stream.Measure)[m]
			try:
				for n in mea.notesAndRests:
					if n.beat%1 == 0.0: 
						if n.isRest:
							orch[p].append(0)
						else:
							orch[p].append(1)
			except:
				print('exception: most likely an error in the voicing of the musicxml score',\
					  'part ',p,'measure ',m)
	orch = np.asarray(orch).T
	if len(orch.shape) == 1:
		print('WARNING: the number of beats per part is not constant')
		print('         check the musicxml file for internal consistency')
		a = []
		for i in range(orch.shape[0]):
			a.append(len(orch[i]))
		clean = np.zeros((min(a),orch.shape[0]),dtype=int)
		for j in range(orch.shape[0]):
			for i in range(min(a)):
				clean[i,j] = orch[j][i]
		orch = clean
	try:
		num = np.zeros(orch.shape[0],dtype=int)
		for n in range(orch.shape[0]):
			num[n] = int(''.join(str(x) for x in orch[n,:]), base=2)
	except:
		num = None
	if barplot:
		axprops = dict(xticks=[], yticks=[])
		barprops = dict(aspect='auto', cmap=plt.cm.binary, interpolation='nearest')
		fig = plt.figure()
		ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
		ax1.matshow(orch[:].T, **barprops)
		plt.show()
		
	return(score,orch,num)

def orchestralNetwork(seq):
	
	''' 
	•	generates the directional network of orchestration vectors from any score in musicxml format
	•	seq (int) – list of orchestration vectors extracted from the score
	•	use orchestralScore() to import the score data as sequence
	'''
	# build the directional network of the full orchestration progression

	dedges = pd.DataFrame(None,columns=['Source','Target','Weight'])
	dnodes = pd.DataFrame(None,columns=['Label'])
	for n in range(len(seq)):
		nameseq = pd.DataFrame([np.array2string(seq[n]).replace(" ","").replace("[","").replace("]","")],\
							   columns=['Label'])
		dnodes = dnodes.append(nameseq)
	df = np.asarray(dnodes)
	dnodes = pd.DataFrame(None,columns=['Label'])
	dff,idx = np.unique(df,return_inverse=True)
	for n in range(dff.shape[0]):
		nameseq = pd.DataFrame([[str(dff[n])]],columns=['Label'])
		dnodes = dnodes.append(nameseq)
	for n in range(1,len(seq)):
		a = np.asarray(seq[n-1])
		b = np.asarray(seq[n])
		pair,r = minimalDistance(a,b)
		tmp = pd.DataFrame([[str(idx[n-1]),str(idx[n]),str(pair+0.1)]],
						   columns=['Source','Target','Weight'])
		dedges = dedges.append(tmp)
	
	# evaluate average degree and modularity
	gbch = nx.from_pandas_dataframe(dedges,'Source','Target','Weight',create_using=nx.DiGraph())
	gbch_u = nx.from_pandas_dataframe(dedges,'Source','Target','Weight')
	# modularity 
	part = cm.best_partition(gbch_u)
	modul = cm.modularity(part,gbch_u)
	# average degree
	nnodes=gbch.number_of_nodes()
	avgdeg = sum(gbch.in_degree().values())/float(nnodes)
		
	return(dnodes,dedges,avgdeg,modul,part)

def orchestralVectorColor(orch,dnodes,part,color=plt.cm.binary):
	'''
	Produces the sequence of the orchestration vectors color-coded according to the modularity class they belong
	Requires the output of orchestralNetwork()
	'''
	pdict = pd.DataFrame(None,columns=['vec','part'])
	for n in range(len(part)):
		tmp = pd.DataFrame( [[dnodes.iloc[int(list(part.keys())[n])][0], list(part.values())[n]]], columns=['vec','part'] )
		pdict = pdict.append(tmp)
	dict_vec = pdict.set_index("vec", drop = True)
	orch_color = np.zeros(orch.shape)
	for i in range(orch.shape[0]):
		orch_color[i,:] = orch[i,:] * \
			(dict_vec.loc[np.array2string(orch[i][:]).replace(" ","").replace("[","").replace("]","")][0]+1)

	axprops = dict(xticks=[], yticks=[])
	barprops = dict(aspect='auto', cmap=color, interpolation='nearest')
	fig = plt.figure()
	ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
	ax1.matshow(orch_color[:].T, **barprops)
	plt.show()

def computeMFCC(input_path,input_file,barplot=True,zero=True,nmel=16):
	# read audio files in repository and compute the MFCC
	waves = list(glob.glob(os.path.join(input_path,input_file)))
	mfcc0 = []
	for wav in np.sort(waves):
		y, sr = librosa.load(wav)
		S = librosa.feature.melspectrogram(y, sr=sr, n_mels=nmel)
		log_S = librosa.power_to_db(S, ref=np.max)
		mfcc = librosa.feature.mfcc(S=log_S, n_mfcc=13)
#		# Here we take the average over a single impulse (for lack of a better measure...)
#		mfcc0.append(np.sum(mfcc,axis=1)/mfcc.shape[1])
		# use mfcc[0] as weighting function for the average of the mfcc's over the full impulse
		mfnorm = (mfcc[0]-np.min(mfcc[0]))/np.max(mfcc[0]-np.min(mfcc[0]))
		mfcc0.append(mfcc.dot(mfnorm)/mfcc.shape[1])
	if zero:
		mfcc0 = np.asarray(mfcc0)
		mfcc[0] = mfnorm
	else:
		# take out the zero-th MFCC - DC value (power distribution)
		temp = np.asarray(mfcc0)
		mfcc0 = temp[:,1:]

	if barplot:
		# print the mfcc0 matrix for all sounds
		axprops = dict(xticks=[], yticks=[])
		barprops = dict(aspect='auto', cmap=plt.cm.coolwarm, interpolation='nearest')
		fig = plt.figure()
		ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
		cax = ax1.matshow(np.flip(mfcc0.T), **barprops)
		fig.colorbar(cax)
		plt.show()
	
	return(np.sort(waves),np.ascontiguousarray(mfcc0),mfcc)
	
def computeStandardizedMFCC(input_path,input_file,nmel=16,nmfcc=13):
	# read audio files in repository and compute the standardized (equal number of samples per file) 
	# and normalized MFCC
	waves = list(glob.glob(os.path.join(input_path,input_file)))
	wf = []
	for wav in np.sort(waves):
		y, sr = librosa.load(wav)
		wf.append(y)
	wf = np.asarray(wf)
	# standardization of the number of sample in every sound wav
	lwf = []
	for n in range(wf.shape[0]):
		lwf.append(wf[n].shape[0])
	lwf = np.asarray(lwf)
	lmax = np.max(lwf)
	mfcc = []
	for n in range(wf.shape[0]):
		wf[n] = np.pad(wf[n], (0, lmax-wf[n].shape[0]), 'constant')
		S = librosa.feature.melspectrogram(wf[n], sr=sr, n_mels=nmel)
		log_S = librosa.power_to_db(S, ref=np.max)
		temp = librosa.feature.mfcc(S=log_S, n_mfcc=nmfcc)
		# normalize mfcc[0] first
		temp[0] = (temp[0]-np.min(temp[0]))/np.max(temp[0]-np.min(temp[0]))
		temp = np.abs(temp)
		maxtemp = np.max(temp[1:])
		temp[1:] = temp[1:]/maxtemp
		mfcc.append(temp)
	mfcc = np.asarray(mfcc)
	return(np.sort(waves),mfcc)
		
def computeCompMPS(input_path,input_file,n_mels=13,barplot=True):
	# read audio files in repository and compute the MPS
	waves = list(glob.glob(os.path.join(input_path,input_file)))
	mps0 = []
	for wav in np.sort(waves):
		y, sr = librosa.load(wav)
		S = librosa.feature.melspectrogram(y, sr=sr, n_mels=n_mels)
		# Here we decompose the MPS in a one-dim component and an activation matrix
		comps, acts = librosa.decompose.decompose(S, n_components=1,sort=True)
		comps = np.reshape(comps,comps.shape[0])
		mps0.append(comps)
	mps0 = np.array(mps0)
	if barplot:
		# print the mps0 matrix for all sounds
		axprops = dict(xticks=[], yticks=[])
		barprops = dict(aspect='auto', cmap=plt.cm.coolwarm, interpolation='nearest')
		fig = plt.figure()
		ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
		cax = ax1.matshow(np.flip(mps0.T,axis=0), **barprops)
		fig.colorbar(cax)
		plt.show()
	return(np.sort(waves),mps0)
	
def timbralNetwork(waves,vector,thup=10,thdw=0.1):
	
	''' 
	•	generates the network of MFCC vectors from sound recordings
	•	seq – list of MFCC vectors
	•	waves - names of wave files
	'''
	# build the network

	dedges = pd.DataFrame(None,columns=['Source','Target','Weight'])
	dnodes = pd.DataFrame(None,columns=['Label'])
	for n in range(len(waves)):
		nameseq = pd.DataFrame([waves[n].split('/')[-1].split('.')[0]],columns=['Label'])
		dnodes = dnodes.append(nameseq)
	df = np.asarray(dnodes)
	dnodes = pd.DataFrame(None,columns=['Label'])
	dff,idx = np.unique(df,return_inverse=True)
	for n in range(dff.shape[0]):
		nameseq = pd.DataFrame([[str(dff[n])]],columns=['Label'])
		dnodes = dnodes.append(nameseq)
	
	N = vector.shape[0]
	index = np.linspace(0,vector.shape[0]-1,vector.shape[0],dtype=int)
	# parallelize over interval vector to optimize the vectorization in sklm.pairwise_distances
	ini,end = load_balancing(size, rank, N)
	nsize = end-ini
	vaux = scatter_array(vector)
	#pair = sklm.pairwise_distances(vaux,vector,metric=distance)
	dedges = pd.DataFrame(None,columns=['Source','Target','Weight'])
	for i in range(nsize):
		tmp = pd.DataFrame(None,columns=['Source','Target','Weight'])
		tmp['Source'] = (i+ini)*np.ones(vector.shape[0],dtype=int)[:]
		tmp['Target'] = index[:]
		tmp['Weight'] = np.sqrt(np.sum((vaux[i,:]-vector[:,:])**2,axis=1))
		tmp = tmp.query('Weight<='+str(thup)).query('Weight>='+str(thdw))
		dedges = dedges.append(tmp)
			
	dedges = dedges.query('Weight<='+str(thup)).query('Weight>='+str(thdw))
	dedges['Weight'] = dedges['Weight'].apply(lambda x: 1/x)
	# do some cleaning
	cond = dedges.Source > dedges.Target
	dedges.loc[cond, ['Source', 'Target']] = dedges.loc[cond, ['Target', 'Source']].values
	dedges = dedges.drop_duplicates(subset=['Source', 'Target'])

	# write csv for partial edges
	dedges.to_csv('edges'+str(rank)+'.csv',index=False)
	comm.Barrier()
	
	if size != 1 and rank == 0:
		dedges = pd.DataFrame(None,columns=['Source','Target','Weight'])
		for i in range(size):
			tmp = pd.read_csv('edges'+str(i)+'.csv')
			dedges = dedges.append(tmp)
			os.remove('edges'+str(i)+'.csv')
		# do some cleaning
		cond = dedges.Source > dedges.Target
		dedges.loc[cond, ['Source', 'Target']] = dedges.loc[cond, ['Target', 'Source']].values
		dedges = dedges.drop_duplicates(subset=['Source', 'Target'])
		# write csv for edges
		dedges.to_csv('edges.csv',index=False)
	elif size == 1:
		os.rename('edges'+str(rank)+'.csv','edges.csv')

	return(dnodes,dedges)
	
def init_list_of_objects(size):
	# initialize a list of list object
	list_of_objects = list()
	for i in range(0,size):
		list_of_objects.append( list() ) #different object reference each time
	return list_of_objects

def minimalDistance(a,b,TET=12,distance='euclidean'):
	'''
	•	calculates the minimal distance between two pcs of same cardinality (bijective)
	•	a,b (int) – pcs as numpy arrays or lists
	'''
	a = np.asarray(a)
	b = np.asarray(b)
	n = a.shape[0]
	if a.shape[0] != b.shape[0]:
		print('dimension of arrays must be equal')
		sys.exit()
	a = np.sort(a)
	iTET = np.vstack([np.identity(n,dtype=int)*TET,-np.identity(n,dtype=int)*TET])
	iTET = np.vstack([iTET,np.zeros(n,dtype=int)])
	diff = np.zeros(2*n+1,dtype=float)
	v = []
	for i in range(2*n+1):
		r = np.sort(b - iTET[i])
		diff[i] = sklm.pairwise_distances(a.reshape(1, -1),r.reshape(1, -1),metric=distance)[0]
		v.append(r)
	imin = np.argmin(diff)
	return(diff.min(),np.asarray(v[imin]).astype(int))

def fetchWaves(url):
	# fetch wave files from remote web repository
	html_page = urllib.request.urlopen(url)
	soup = BeautifulSoup(html_page)
	for link in soup.findAll('a'):
		if 'wav' in link.get('href'):
			print(link.get('href'))
			wget.download(link.get('href'))

def normSoundDecay(signal,sr,zero=1.0e-10,plot=False):
	# evaluate the normalized sound decay envelope
	t = np.arange(len(signal))/sr
	analytic_signal = hilbert(signal)
	amplitude_envelope = np.abs(analytic_signal)
	maxsp = int(np.argwhere(np.abs(signal) < zero)[0])
	alpha = np.poly1d(np.polyfit(t[:maxsp],np.log(amplitude_envelope[:maxsp]),1))
	if plot:
		plt.plot(t[:maxsp],np.log(amplitude_envelope[:maxsp]))
		tp = np.linspace(0,t[maxsp],200)
		plt.plot(tp,alpha(tp),'.')
		plt.show()
	return(np.abs(alpha[1]),alpha,t)

def normSoundDecay2(signal,sr,maxsp=None,zero=1.0e-10,plot=False):
	# evaluate the normalized sound decay envelope
	t = np.arange(len(signal)) #/sr
	analytic_signal = hilbert(signal)
	amplitude_envelope = np.abs(analytic_signal)
	idmax = np.argwhere(amplitude_envelope == np.max(amplitude_envelope))[0,0]
	amplitude_envelope = amplitude_envelope[idmax:]
	if maxsp == None: maxsp = len(amplitude_envelope)-1 #int(np.argwhere(np.abs(signal) < zero)[0])
	alpha = np.poly1d(np.polyfit(t[:maxsp],np.log(amplitude_envelope[:maxsp]),1))
	if plot:
		plt.plot(t[:maxsp],np.log(amplitude_envelope[:maxsp]))
		tp = np.linspace(0,t[maxsp],200)
		plt.plot(tp,alpha(tp),'.')
		plt.show()
	return(np.abs(alpha[1]),alpha,t)

def mfccSoundDecay(mfcc,maxidx=25,plot=False):
	# evaluate the normalized sound decay envelope from the MFCC
	idmax = np.argwhere(mfcc == np.max(mfcc))[0,0]
	mfcc = mfcc[idmax:]
	t = np.arange(len(mfcc))
	mfcc = mfcc-np.min(mfcc)
	mfcc = np.log(mfcc[mfcc>1.e-10])
	if plot:
		plt.plot(mfcc)
	if maxidx > mfcc.shape[0]: maxidx = mfcc.shape[0]
	alpha,res,_,_,_ = np.polyfit(t[:maxidx],mfcc[:maxidx],1,full=True)
	alpha = np.poly1d(alpha)
	if plot:
		plt.plot(t[:maxidx],mfcc[:maxidx])
		tp = np.linspace(0,t[maxidx],50)
		plt.plot(tp,alpha(tp),'.')
		plt.show()
	return(np.abs(alpha[1]),alpha,t,res)
	
def mfccSoundDecayOptimal(mfcc,plot=False):
	tmp = []
	for i in range(5,300):
		a,_,_,res = mfccSoundDecay(mfcc,maxidx=i,plot=False)
		tmp.append([i,a,res/i])
	tmp = np.asarray(tmp)
	idx = argrelextrema(tmp[:,2], np.less)[0][-1]
	a,_,_,_ = mfccSoundDecay(mfcc,maxidx=idx,plot=plt)
	return(a)

def mfccSoundDecayPiecewise(mfcc,breakpoints=[],plot=False):
	idmax = np.argwhere(mfcc == np.max(mfcc))[0,0]
	y = mfcc[idmax:100]
	y = y-np.min(y)
	y = np.log(y[y>1.e-10])
	x = np.arange(len(y))

	initialBreakpoints = breakpoints
	xfit,yfit = SegmentedLinearReg( x, y, initialBreakpoints )
	if plot:
		plt.plot( x, y, 'ok' )
		plt.plot( xfit,yfit, '-r' );
		plt.xlabel('X'); plt.ylabel('Y')
	# Evaluate residual (np.abs(a*x+b-mfcc)/len(mfcc))
	line = np.zeros(x.shape,dtype=float)
	a = []
	b = []
	for n in range(1,xfit.shape[0]):
		a0 = (yfit[n]-yfit[n-1])/(xfit[n]-xfit[n-1])
		b0 = yfit[n-1]-a0*xfit[n-1]
		a.append(a0)
		b.append(b0)
		for i in range(x.shape[0]):
			if x[i] >= xfit[n-1] and x[i] <= xfit[n]:
				line[i] = a0*x[i]+b0
	res = np.sum(np.abs(y-line)/x.shape[0])
	if plot:
		plt.plot(x,line)
	return(a,b,xfit,yfit,res)

def minimizeBKPT(vec,method='MC',nstep=100,extrema=[(0,20),(15,40),(30,60)]):

	def func(x,*args):
		return(mfccSoundDecayPiecewise(vec,breakpoints=x,plot=False)[4])

	if method == 'MC':
		# MonteCarlo optimization of breakpoints for piecewise fitting
		# needs nstep
		xopt = [1,1,1]
		res = res0 = 10
		for n in range(nstep):
			x = np.sort([np.random.randint(1,20),np.random.randint(1,40),np.random.randint(1,80)])
			try:
				res = func(x,vec)
			except:
				pass
			if res < res0:
				xopt = np.sort(x)
				res0 = res
	elif method == 'uniform':
		# find minimum of residual on a uniform grid
		# needs extrema as list of tuples
		x = []
		for i in range(extrema[0][0],extrema[0][1]):
			for j in range(extrema[1][0],extrema[1][1]):
				for k in range(extrema[2][0],extrema[2][1]):
					x.append([i,j,k])
		x = np.asarray(x)
		res = []
		xres = []
		for n in range(x.shape[0]):
			try:
				res.append(func(np.sort(x[n]),vec))
				xres.append(x[n])
			except:
				pass
		res = np.asarray(res)
		xres = np.asarray(xres)
		r = res[~np.isnan(res)]
		xopt = np.sort(xres[np.argwhere(res==np.min(r))][0,0])
		res0 = res[np.argwhere(res==np.min(r))][0,0]

	return(res0,xopt)
			
def computeASCBW(input_path,input_file,zero=1.0e-10,barplot=True):
	# sound descriptor as normalized sound decay (alpha), spectral centoid and spectral bandwidth
	# as in Aramaki et al. 2009
	waves = list(glob.glob(os.path.join(input_path,input_file)))
	ascbw = []
	for wav in np.sort(waves):
		y, sr = librosa.load(wav)
		maxsp = int(np.argwhere(np.abs(y) < zero)[0])
		try:
			alpha0,_,_ = normSoundDecay(y,sr,plot=False)
		except:
			onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
			y = y[(onset_frames[0]+1):]
			maxsp = int(np.argwhere(np.abs(y) < zero)[0])
			alpha0,_,_ = normSoundDecay(y,sr,plot=False)
		cent = librosa.feature.spectral_centroid(y=y, sr=sr,hop_length=maxsp)
		spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr,hop_length=maxsp)
#		ascbw.append([alpha0,cent[0,0],spec_bw[0,0]])
		ascbw.append([alpha0/cent[0,0],cent[0,0],spec_bw[0,0]])
	ascbw = np.asarray(ascbw)
	# normalization to np.max
	for i in range(3):
		ascbw[:,i] /= np.max(ascbw[:,i])
	
	if barplot:
		# print the ascbw matrix for all sounds
		axprops = dict(xticks=[], yticks=[])
		barprops = dict(aspect='auto', cmap=plt.cm.coolwarm, interpolation='nearest')
		fig = plt.figure()
		ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
		cax = ax1.matshow(ascbw.T, **barprops)
		fig.colorbar(cax)
		plt.show()
	return(np.sort(waves),ascbw)

def computeModifiedASCBW(input_path,input_file,zero=1.0e-10,scnd=False,method='MC',nstep=500,barplot=True):
	# sound descriptor as normalized sound decay from the fit of the 0-th component of the MFCC, 
	# spectral centoid and spectral bandwidth
	waves = list(glob.glob(os.path.join(input_path,input_file)))
	ascbw = []
	for wav in np.sort(waves):
		y, sr = librosa.load(wav)
		maxsp = int(np.argwhere(np.abs(y) < zero)[0])
		cent = librosa.feature.spectral_centroid(y=y, sr=sr,hop_length=maxsp)
		spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr,hop_length=maxsp)
		S = librosa.feature.melspectrogram(y, sr=sr, n_mels=16)
		log_S = librosa.power_to_db(S, ref=np.max)
		mfcc = librosa.feature.mfcc(S=log_S, n_mfcc=13)
		try:
			a,_,_,_,_ = mfccSoundDecayPiecewise(mfcc[0],breakpoints=minimizeBKPT(mfcc[0],method=method,nstep=nstep)[1],plot=False)
		except:
			print(wav)
			break
		alpha0 = a[0]
		if np.abs(a[1]) > np.abs(a[2]): a[1] = a[2]
		if a[1] > 0: a[1] = 0
		alpha1 = a[1]
		if scnd: 
			ascbw.append([np.abs(alpha0),np.abs(alpha1),cent[0,0],spec_bw[0,0]])
			na = 4
		else:
			ascbw.append([np.abs(alpha0),cent[0,0],spec_bw[0,0]])
			na = 3
	ascbw = np.asarray(ascbw)
	# normalization to np.max
	ascbwu = np.zeros(ascbw.shape,dtype=float)
	for i in range(na):
		ascbwu[:,i] = ascbw[:,i]
		ascbw[:,i] /= np.max(ascbw[:,i])

	if barplot:
		# print the ascbw matrix for all sounds
		axprops = dict(xticks=[], yticks=[])
		barprops = dict(aspect='auto', cmap=plt.cm.coolwarm, interpolation='nearest')
		fig = plt.figure()
		ax1 = fig.add_axes([0.1, 0.1, 3.1, 0.7], **axprops)
		cax = ax1.matshow(ascbw.T, **barprops)
		fig.colorbar(cax)
		plt.show()
	return(np.sort(waves),ascbw,ascbwu)

def analyzeTimbre(soundfile,outlist=[],zero=1.0e-10,plot=True,crm=True,tms=True,xml=False,mps=True):
	var = {}        
	# load soundfile
	y, sr = librosa.load(soundfile)
	var['y'] = y
	var['sr'] = sr
	# analyze onsets
	o_env = librosa.onset.onset_strength(y, sr=sr)
	times = librosa.frames_to_time(np.arange(len(o_env)), sr=sr)
	onset_frames = librosa.onset.onset_detect(onset_envelope=o_env, sr=sr)
	var['onset_frames'] = onset_frames
	var['times'] = times
	# analyze decay constants and specral features
	maxsp = int(np.argwhere(np.abs(y) < zero)[0])
	a,alpha,t = normSoundDecay(y[onset_frames[0]:],sr,plot=True)
	print('normalized sound decay constant = ',a.round(3))
	cent = librosa.feature.spectral_centroid(y=y, sr=sr,hop_length=maxsp)
	print('spectral centroid = ',cent[0][0])
	spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr,hop_length=maxsp)
	print('spectral bandwidth = ',spec_bw[0][0])
	if plot:
		plt.figure(figsize=(18,8))
		ax1 = plt.subplot(2, 1, 1)
		librosa.display.waveplot(y[:])
		plt.title('Waveshape')
		plt.subplot(2, 1, 2, sharex=ax1)
		plt.plot(times, o_env, label='Onset strength')
		plt.vlines(times[onset_frames], 0, o_env.max(), color='r', alpha=0.9,linestyle='--', label='Onsets')
		plt.axis('tight')
		plt.legend(frameon=True, framealpha=0.75)
	p = None
	if crm:
		chroma = librosa.feature.chroma_stft(y=y, sr=sr)
		var['chroma'] = chroma
		nseq = []
		for i in range(onset_frames.shape[0]-1):
			nseq.append(np.argwhere(chroma[:,onset_frames[i]] == 1.0)[0,0])
		var['nseq'] = PCSet(nseq,UNI=False,ORD=False)
		if plot:
			plt.figure(figsize=(18, 4))
			librosa.display.specshow(chroma, y_axis='chroma', x_axis='time')
			plt.colorbar()
			plt.title('Chromagram')
			plt.tight_layout()
		idx = np.argwhere(chroma == 1.0)
		p = np.histogram(idx[:,0],12)
		var['prob'] = np.asarray(p[0]/np.sum(p[0]))
		if plot:
			c = np.array(['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'])
			plt.figure(figsize=(6, 4))
			plt.bar(c,p[0],width=0.8)
	if plot: plt.show()
	tempo = None
	if tms:
		tempo = librosa.beat.tempo(onset_envelope=o_env, sr=sr)
		beat = librosa.frames_to_time(onset_frames, sr=sr)
		beat = RHYTHMSeq((np.diff(beat)*16).round(0)/16,REF='e')
		var['beat'] = beat
		var['tempo'] = int(tempo[0])
		if plot: beat.displayRhythm(xml)
	if mps:
		# mel-scaled power (energy-squared) spectrogram
		S = librosa.feature.melspectrogram(y, sr=sr, n_mels=16) #,hop_length=len(y))
		# Convert to log scale (dB). We'll use the peak power (max) as reference.
		log_S = librosa.power_to_db(S, ref=np.max)
		librosa.display.specshow(log_S, sr=sr, x_axis='time', y_axis='mel')
		_,_ = computeMFCC('./',soundfile,barplot=True)
	output = []
	for out in outlist:
		output.append(var[out])
	return(output)
	
def SegmentedLinearReg( X, Y, breakpoints ):
	
	import warnings
	warnings.filterwarnings("ignore")
	
	ramp = lambda u: np.maximum( u, 0 )
	step = lambda u: ( u > 0 ).astype(float)  
	nIterationMax = 100

	breakpoints = np.sort( np.array(breakpoints) )

	dt = np.min( np.diff(X) )
	ones = np.ones_like(X)

	for i in range( nIterationMax ):
		# Linear regression:  solve A*p = Y
		Rk = [ramp( X - xk ) for xk in breakpoints ]
		Sk = [step( X - xk ) for xk in breakpoints ]
		A = np.array([ ones, X ] + Rk + Sk )
		p =  lstsq(A.transpose(), Y, rcond=None)[0] 

		# Parameters identification:
		a, b = p[0:2]
		ck = p[ 2:2+len(breakpoints) ]
		dk = p[ 2+len(breakpoints): ]

		# Estimation of the next break-points:
		newBreakpoints = breakpoints - dk/ck 

		# Stop condition
		if np.max(np.abs(newBreakpoints - breakpoints)) < dt/5:
			break

		breakpoints = newBreakpoints
	else:
		pass
#		print( 'maximum iteration reached' )

	# Compute the final segmented fit:
	Xsolution = np.insert( np.append( breakpoints, max(X) ), 0, min(X) )
	ones =  np.ones_like(Xsolution) 
	Rk = [ c*ramp( Xsolution - x0 ) for x0, c in zip(breakpoints, ck) ]

	Ysolution = a*ones + b*Xsolution + np.sum( Rk, axis=0 )

	return (Xsolution, Ysolution)