"""
Extension classes enhance TouchDesigner components with python. An
extension is accessed via ext.ExtensionClassName from any operator
within the extended component. If the extension is promoted via its
Promote Extension parameter, all its attributes with capitalized names
can be accessed externally, e.g. op('yourComp').PromotedFunction().

Help: search "Extensions" in wiki
"""

from TDStoreTools import StorageManager
import TDFunctions as TDF
from pathlib import Path
import os
from urllib.parse import urlparse
import hashlib
from typing import Optional
import pyrfc6266

class STATE:
	WAIT = 'WAIT'
	HEAD = 'HEAD'
	GET = 'GET'
	DOWNLOAD = 'DOWNLOAD'
	DONE = 'DONE'
	EXISTS = 'EXISTS'
	ABORT = 'ABORT'

class RequestObj:

	def __init__(self, url:str, 
					   location:str, 
					   loadIntoProj:bool, 
					   compPath:COMP, 
					   discCopy:bool, 
					   dwnldCopy:bool, 
					   renameTo:str, 
					   doneCallback, 
					   abortCallback,
					   progressCallback, 
					   reqMethod:str, 
					   reqData:dict, 
					   reqPars:dict, 
					   authType:str, 
					   username:str, 
					   password:str, 
					   appKey:str, 
					   appSecret:str, 
					   oauth1Token:str, 
					   oauth1Secret:str, 
					   oauth2Token:str, 
					   clear:bool,
					   showProgress:bool):

		self.stateObj = StateObj()
		self.id = -1
		self.downloadId = -1
		self.downloadHash = None
		# arguments for the webclientDAT
		self.reqMethod = reqMethod
		self.reqData = reqData
		self.reqPars = reqPars
		self.authType = authType
		self.username = username
		self.password = password
		self.appKey = appKey
		self.appSecret = appSecret
		self.oauth1Token = oauth1Token
		self.oauth1Secret = oauth1Secret
		self.oauth2Token = oauth2Token
		self.url = url
		# arguments how to deal with the file
		self.location = location
		self.loadIntoProj = loadIntoProj
		self.compPath = compPath
		self.discCopy = discCopy
		self.renameTo = renameTo
		self.doneCallback = doneCallback
		self.abortCallback = abortCallback
		self.progressCallback = progressCallback
		self.clear = clear
		self.dwnldCopy = dwnldCopy
		# other attributes
		self.contentLength = -1
		self.progress = tdu.Dependency(0)
		self.received = 0
		self.file = None
		self.fileName = None
		self.path = None
		self.realUrl = url
		self.rawData = bytearray()
		self.state = STATE.GET
		self.info = None
		self.startFrame = absTime.frame
		self.endFrame = -1
		self.showProgress = showProgress

		# create the download hash
		if self.renameTo:
			self.fileName = self.renameTo
		else:
			self.fileName = os.path.basename(urlparse(url).path)
		self.downloadHash = hashlib.sha256('{},{},{}'.format(url,location,self.fileName).encode()).hexdigest()
		self.stateObj.downloadHash = self.downloadHash

	@property
	def dwnldCallDict(self):
		callDict = {
			'url' : self.url,
			'location' : self.location,
			'loadIntoProj' : self.loadIntoProj,
			'compPath' : self.compPath,
			'discCopy' : self.discCopy,
			'dwnldCopy' : self.dwnldCopy,
			'renameTo' : self.renameTo, 
			'doneCallback' : self.doneCallback, 
			'abortCallback' : self.abortCallback, 
			'reqMethod' : self.reqMethod, 
			'reqData' : self.reqData, 
			'reqPars' : self.reqPars, 
			'authType' : self.authType, 
			'username' : self.username, 
			'password' : self.password, 
			'appKey' : self.appKey, 
			'appSecret' : self.appSecret, 
			'oauth1Token' : self.oauth1Token, 
			'oauth1Secret' : self.oauth1Secret, 
			'oauth2Token' : self.oauth2Token, 
			'clear' : self.clear,
			'force' : True,
			'showProgress' : self.showProgress
		}
		return callDict

	@property
	def id(self):
		return self._id
	
	@id.setter
	def id(self, reqId:int):
		self._id = reqId
		self.stateObj.id = reqId

	@property
	def fileName(self):
		return self._fileName

	@fileName.setter
	def fileName(self, fileNameStr:str):
		if self.renameTo:
			fileNameStr = self.renameTo

		if fileNameStr is None:
			return
		
		self._fileName = fileNameStr
		self.path = self.location.joinpath(fileNameStr)
		self.stateObj.path = self.path

		# check file extension
		fileExtension = self.path.suffix
		if fileExtension:
			# when only loading into project make sure it is a valid file
			if self.loadIntoProj:
				if fileExtension and (fileExtension != '.tox'):
					self.state = STATE.ABORT
					self.stateObj.info = "only tox files can be loaded into project."
					return

		# check if file already exisits
		# in case of no extension, we'll take care of this later
		if not self.loadIntoProj or (self.loadIntoProj and self.discCopy):
			# check if the file already exists
			if self.path.exists():
				# None: don't download
				# True: append a suffix to the filename
				# False: overwrite, nothing to do here
				if self.dwnldCopy is None:
					self.state = STATE.EXISTS
					self.contentLength = self.path.stat().st_size
					self.received = self.contentLength.peekVal
				elif self.dwnldCopy is True:
					self._fileName = self.newFileName(self.path)
					self.path = self.location.joinpath(self._fileName)
					self.stateObj.path = self.path

	@property
	def received(self):
		return self._received

	@received.setter
	def received(self, length:int):
		self._received = tdu.Dependency(length)
		self.progress.val = self._received / max(self.contentLength, 1)
		# update state object
		self.stateObj.received = self._received
		self.stateObj.progress = self.progress

	@property
	def state(self):
		return self._state

	@state.setter
	def state(self, stateVal:str):
		self._state = stateVal
		# update stateObj
		self.stateObj.state = stateVal

	@property
	def info(self):
		return self._info

	@info.setter
	def info(self, infoVal:str):
		self._info = infoVal
		# update stateObj
		self.stateObj.info = infoVal

	@property
	def contentLength(self):
		return self._contentLength

	@contentLength.setter
	def contentLength(self, length:int):
		self._contentLength = tdu.Dependency(length)
		# update stateObj
		self.stateObj.contentLength = length
	
	@property
	def compPath(self):
		return self._compPath

	@compPath.setter
	def compPath(self, comp:COMP):
		self._compPath = comp
		# update stateObj
		self.stateObj.compPath = comp

	@property
	def startFrame(self):
		return self._startFrame

	@startFrame.setter
	def startFrame(self, frame:int):
		self._startFrame = frame
		# update stateObj
		self.stateObj.startFrame = frame

	@property
	def endFrame(self):
		return self._endFrame

	@endFrame.setter
	def endFrame(self, frame:int):
		self._endFrame = frame
		# update stateObj
		self.stateObj.endFrame = frame

	@property
	def info(self):
		return self._info

	@info.setter
	def info(self, infoStr:str):
		self._info = infoStr
		# update stateObj
		self.stateObj.info = infoStr

	###########
	# methods #
	###########
	def parseHeader(self, headerDict:dict) -> None:
		"""Parses the header dictionary for content-length, redirects and final
		filenames.

		Args:
			headerDict (dict): The headerDict as returned from the webclientDAT.
		"""
		# read the content-length entry
		contentLength = headerDict.get('content-length', None)
		if contentLength is not None:
			self.contentLength = int(contentLength)
		
		# check for a content-disposition header
		contentDisposition = headerDict.get('content-disposition', None)
		if not self.renameTo and contentDisposition:
			self.fileName = pyrfc6266.parse_filename(contentDisposition)	

		# check for a location entry
		realUrl = headerDict.get('location', None)
		if realUrl is not None:
			#update the url
			self.realUrl = realUrl
			# retrieve filename if renameTo is not set and there has been no
			# content-disposition header
			if not self.renameTo and not contentDisposition:
				self.fileName = os.path.basename(urlparse(realUrl).path)
	
	def appendData(self, data:bytes) -> None:
		"""Appends the received data to the file or the raw data attribute for
		insertion into the project at the end of the download process

		Args:
			data (bytes): The received data from the webclientDAT.
		"""

		dataLength = len(data)
		self.received += dataLength
		# if we are writing to disc, try to append the data to the file
		if not self.loadIntoProj or (self.loadIntoProj and self.discCopy):
			if not self.file:
				# create the target folder
				self.location.mkdir(parents=True, exist_ok=True)
				filePath = self.location.joinpath(self.downloadHash+'download')
				try:
					self.file = open(filePath, 'wb')
				except:
					self.state = STATE.ABORT
					self.info = "can't create file {}".format(filePath)
			self.file.write(bytearray(data))
		
		# if this is to be loaded into the project, add data to attribute
		if self.loadIntoProj:
			self.rawData += bytearray(data)

	def finishDwnld(self) -> bool or None:
		"""Function is called if a connection on the webclientDAT is closed.

		Returns:
			bool or None: True if download was sucessful, False if download was aborted, None otherwise.
		"""
		fileDone = False
		dataDone = False

		# close the temporary file
		if self.file:
			self.file.close()
			finalFile = Path(self.file.name)
			fileDone = True
		if self.rawData:
			dataDone = True

		self.endFrame = absTime.frame

		if self.file or self.rawData:
			# if all content is received, rename temporary file and or 
			# place component in project
			if (self.contentLength == -1 and self.state != STATE.ABORT) or self.contentLength == self.received:
				if fileDone:
					finalFile.replace(self.path)
				if dataDone:
					finalCompPath = self.compPath.loadByteArray(self.rawData)
					self.compPath = finalCompPath
				self.state = STATE.DONE
				return True
			# if the file exists, set the state
			elif self.state == STATE.EXISTS:
				return True
			# otherwise there was some kind of error, delete the temporary file.
			else:
				if fileDone:
					finalFile.unlink(missing_ok=True)
				self.state = STATE.ABORT
				self.info = 'incomplete download: {0} of {1}'.format(self.received, self.contentLength)
				return False

	def newFileName(self, filePath:Path):
		"""Expands name portion of filename with numeric ' (x)' suffix to
		return filename that doesn't exist already.

		Args:
			filePath (Path): The Path object of the file.
		"""
		parent = filePath.parent
		stem = filePath.stem
		ext = filePath.suffix
		names = [x for x in os.listdir(parent) if x.startswith(stem)]
		names = [x.rsplit('.', 1)[0] for x in names]
		suffixes = [x.replace(stem, '') for x in names]
		# filter suffixes that match ' (x)' pattern
		suffixes = [x[2:-1] for x in suffixes
					if x.startswith(' (') and x.endswith(')')]
		indexes  = [int(x) for x in suffixes
					if set(x) <= set('0123456789')]
		idx = 1
		if indexes:
			idx += sorted(indexes)[-1]
		newFileName = '%s (%d)%s' % (stem, idx, ext) 
		return newFileName
				

class StateObj:
	def __init__(self):
		self.id = None
		self.downloadHash = None
		self.state = STATE.GET
		self.path = None
		self.compPath = None
		self.contentLength = 0
		self.received = 0
		self.progress = 0
		self.startFrame = 0
		self.endFrame = -1
		self.info = None
		self.dictVal = {}
	
	@property
	def dictVal(self):
		returnDict = {
			'id' : self.id,
			'downloadHash' : self.downloadHash,
			'state' : self.state,
			'path' : self.path,
			'compPath' : self.compPath,
			'contentLength' : self.contentLength,
			'received' : self.received,
			'progress' : self.progress,
			'startFrame' : self.startFrame,
			'endFrame' : self.endFrame,
			'info' : self.info
		}
		return returnDict
	
	@dictVal.setter
	def dictVal(self, dictValue):
		self._dictVal = dictValue

class FileDownloaderExt:
	"""
	FileDownloaderExt description
	"""
	def __init__(self, ownerComp):
		# The component to which this extension is attached
		self.ownerComp = ownerComp

		# properties
		TDF.createProperty(self, 'requestDict', value={}, dependable='deep',
						   readOnly=False)
		TDF.createProperty(self, 'stateDict', value={}, dependable='deep',
						   readOnly=False)
		TDF.createProperty(self, 'dwnldQueue', value=[], dependable='deep',
						   readOnly=False)

	def Download(self, url:str = None, location:str = None, loadIntoProj:bool = False, 
				 compPath:COMP = None, discCopy:bool = False, dwnldCopy:Optional[bool] = None, 
				 renameTo:str = None, doneCallback=None, abortCallback=None, progressCallback=None, reqMethod:str = 'GET', 
				 reqData:dict = {}, reqPars:dict = {}, authType=None, username=None, 
				 password=None, appKey=None, appSecret=None, oauth1Token=None, oauth1Secret=None, 
				 oauth2Token=None, uploadFile=None, force:bool = False, clear:bool = True, showProgress:Optional[bool]=None) -> dict:
		"""_summary_

		Args:
			url (str, optional): The url to download the data from. Defaults to None.
			location (str, optional): The location to save the file to. Defaults to None.
			dwnldCopy (Optional[bool], optional): Defines how to deal with already existing files: 
												  None - return existing file path
												  True - create a copy of the file.
												  False - overwrite the existing file. 
												  Defaults to None.
			renameTo (str, optional): The final name of the downloaded file. Defaults to None.
			doneCallback (_type_, optional): A custom callback function called when the download has successfully finished. Defaults to None.
			abortCallback (_type_, optional): A custom callback function called when the download was aborted. Defaults to None.
			reqMethod (str, optional): The HTTP request method used for the download. Defaults to 'GET'.
			reqData (dict, optional): The data to send in the body of the request. Defaults to {}.
			reqPars (dict, optional): Query parameters for the request. The parameters will be URL-encoded and appended to the URL. Defaults to {}.
			force (bool, optional): Forces the download skipping the queue. Defaults to False.
			clear (bool, optional): Set to false if the stateDict response should stick around for a final call of this function after successfully 
									downloading or aborting the download. This is useful when an external call keeps probing this functions to return the 
									state of the download. Defaults to True.

		Returns:
			dict: A state dictionary.
		"""

		webClient = self.ownerComp.op('webclient1')
		if not url:
			url = self.ownerComp.par.Url.eval()
		if not location:
			location = self.ownerComp.par.Location.eval()
		if showProgress is None:
			showProgress = self.ownerComp.par.Showprogress.eval()

		# create RequstObj
		requestObj = RequestObj(
			url,
			Path(location),
			loadIntoProj,
			compPath,
			discCopy,
			dwnldCopy,
			renameTo,
			doneCallback,
			abortCallback,
			progressCallback,
			reqMethod,
			reqData,
			reqPars,
			authType,
			username,
			password,
			appKey,
			appSecret,
			oauth1Token,
			oauth1Secret,
			oauth2Token,
			clear,
			showProgress
		)
		stateObj = requestObj.stateObj
		if stateObj.state in [STATE.EXISTS]:
			return stateObj.dictVal

		# return the stateDict if it can be found
		thisStateObj = self.stateDict.get(requestObj.downloadHash, None)

		if thisStateObj:
			if thisStateObj.state in [STATE.DONE, STATE.ABORT, STATE.EXISTS]:
				retState = self.stateDict.pop(requestObj.downloadHash)
				return retState.dictVal
			elif thisStateObj.state in [STATE.HEAD, STATE.GET, STATE.WAIT] and not force:
				retState = self.stateDict[requestObj.downloadHash]
				return retState.dictVal

		# deal with queue
		if len(self.requestDict) >= self.ownerComp.par.Maxdownloads.eval() and not force:
			requestObj.state = STATE.WAIT
			self.dwnldQueue.append(requestObj)
			self.stateDict[requestObj.downloadHash] = requestObj.stateObj
			return requestObj.stateObj.dictVal
	
		# get file
		reqId = webClient.request(url, reqMethod, data=reqData, pars=reqPars, authType=authType, username=username, password=password, appKey=appKey, appSecret=appSecret, oauth1Token=oauth1Token, oauth1Secret=oauth1Secret, oauth2Token=oauth2Token, uploadFile=uploadFile)
		requestObj.id = reqId
		self.requestDict[reqId] = requestObj

		self.stateDict[requestObj.downloadHash] = requestObj.stateObj

		return self.stateDict[requestObj.downloadHash].dictVal

	def parseResponse(self, webClientDAT:webclientDAT, statusCode:dict, headerDict:dict, data:bytes, id:int) -> None:
		"""This function parses the response received by a webclientDAT's onResponse callback 

		Args:
			webClientDAT (webclientDAT): The webclientDAT receiving the response.
			statusCode (dict): The status code of the response, formatted as a dictionary with two key-value pairs: 'code', 'message'.
			headerDict (dict): The header of the response from the server formatted as a dictionary. Only sent once when streaming.
			data (bytes): The data of the response
			id (int): The request's unique identifier

		Raises:
			Exception: _description_
		"""
		thisRequestObj = self.requestDict.get(id, None)
		# return if connection was already dealt with
		if not thisRequestObj:
			return

		thisRequestObj.parseHeader(headerDict)

		# deal with response codes [ERROR]
		if statusCode['code'] >= 400:
			self.errorResponse(webClientDAT, statusCode, id)
					
		# deal with response codes [REDIRECT]
		elif statusCode['code'] > 300:
			self.redirectResponse(headerDict, id)

		# deal with response codes [OK]
		elif statusCode['code'] < 300:
			self.okResponse(webClientDAT, statusCode, headerDict, data, id)

		return

	def disconnect(self, webClientDAT:webclientDAT, id:int):
		"""Function is called when the webclient disconnects from the server.
		   If a file was being downloaded, it checks if the expected size was
		   transfered and either renames the temporary file to the real fileName
		   or removes the temporary file from the folder.

		Args:
			webClientDAT (webclientDAT): The webclientDAT receiving the response.
			id (int): id of the connection severend.
		"""
		thisRequestObj = self.requestDict.pop(id)
		downloadHash = thisRequestObj.downloadHash
	
		thisStateObj = self.stateDict.get(downloadHash, None)
		if thisStateObj is None:
			self.queueNext()
			self.closeProgress()
			del thisRequestObj
			return

		thisRequestObj.finishDwnld()
		if thisRequestObj.state == STATE.ABORT:
			self.ownerComp.DoCallback('onDownloadAborted', thisRequestObj.stateObj.dictVal, callbackOrDat=thisRequestObj.abortCallback)
			if thisRequestObj.clear:
				thisStateObj = self.stateDict.pop(downloadHash)
				del thisStateObj
			self.queueNext()
			self.closeProgress()
			del thisRequestObj
			return

		elif thisRequestObj.state in [STATE.EXISTS, STATE.DONE]:
			self.ownerComp.DoCallback('onFileDownloaded', thisRequestObj.stateObj.dictVal, callbackOrDat=thisRequestObj.doneCallback)
			if thisRequestObj.clear:
				thisStateObj = self.stateDict.pop(downloadHash)
				del thisStateObj
			self.queueNext()
			self.closeProgress()
			del thisRequestObj
			return

		return

	def Abort(self, downloadHash:str):
		"""This function aborts a download or removes it from the download queue.

		Args:
			id (str): The downloadId string which is usually returned in the stateDict
					  upon calling .Download()
		"""
		if self.stateDict.get(downloadHash, None) is not None:
			self.stateDict[downloadHash].info = 'user initiated abort'
			reqId = self.stateDict[downloadHash].id
			self.ownerComp.op('webclient1').closeConnection(reqId)
		queueLen = len(self.dwnldQueue)
		for i in range(queueLen):
			if self.dwnldQueue[queueLen-1-i]['downloadId'] == downloadHash:
				self.dwnldQueue.pop(queueLen-1-i)

	def AbortAll(self):
		"""Close all open webclientDAT connections and empty out the request, 
		state, and dwnldQueue collections.
		"""
		self.dwnldQueue = []
		if self.stateDict:
			for i in self.stateDict:
				self.stateDict[i].state = STATE.ABORT
				self.stateDict[i].info = 'user initiated abort'
		if self.requestDict:
			for i in self.requestDict:
				self.requestDict[i].state = STATE.ABORT
				self.requestDict[i].info = 'user initiated abort'
				file = self.requestDict[i].file
				if file:
					file.close()

		webClientDat = self.ownerComp.op('webclient1')
		for i in webClientDat.connections:
			webClientDat.closeConnection(i)
		self.requestDict = {}
		self.stateDict = {}

	def queueNext(self):
		# empty queue
		if self.dwnldQueue:
			nextDwnld = self.dwnldQueue.pop(0)
			self.Download(**nextDwnld.dwnldCallDict)
			del nextDwnld

	def errorResponse(self, webClientDAT:webclientDAT, statusCode:dict, id:int):
		"""This function deals with any response that has an error code.

		Args:
			statusCode (dict): _description_
			id (int): _description_
		"""
		thisRequestObj = self.requestDict.get(id, {})
		thisRequestObj.state = STATE.ABORT
		thisRequestObj.info = statusCode

	def redirectResponse(self, headerDict:dict, id:int):
		"""This function deals with any response that has a redirect code.

		Args:
			headerDict (dict): _description_
			id (int): _description_
		"""

		return

	def okResponse(self, webClientDAT:webclientDAT, statusCode:dict, headerDict:dict, data:bytes, id:int):
		"""This function deals with any responses that have a status code of
		smaller 300.

		Args:
			webClientDAT (webclientDAT): _description_
			headerDict (dict): _description_
			data (bytes): _description_
			id (int): _description_
		"""
		thisRequestObj = self.requestDict.get(id, {})

		# something had set the state to fail --> abort
		if thisRequestObj.state in [STATE.ABORT, STATE.EXISTS]:
			webClientDAT.closeConnection(id)
			return

		if statusCode['code'] == 200:
			thisRequestObj.appendData(data)
			if thisRequestObj.progressCallback is not None:
				self.ownerComp.DoCallback('onFileProgress', thisRequestObj.stateObj.dictVal, callbackOrDat=thisRequestObj.progressCallback)
			self.openProgress(thisRequestObj.showProgress)

		# if state is GET, proceed with processing data 
		elif thisRequestObj.state == STATE.GET:
			thisRequestObj.appendData(data)
			if thisRequestObj.progressCallback is not None:
				self.ownerComp.DoCallback('onFileProgress', thisRequestObj.stateObj.dictVal, callbackOrDat=thisRequestObj.progressCallback)

	# utility
	def openProgress(self, showProgress):
		"""Opens the progress panel if that option is selected.
		"""
		if showProgress:
			winComp = self.ownerComp.op('window_download')
			if not winComp.isOpen:
				winComp.par.winopen.pulse()

	def closeProgress(self):
		"""Closes the progress window if nothing else is downloading or queued.
		"""
		if not self.requestDict and not self.dwnldQueue:
			winComp = self.ownerComp.op('window_download')
			if winComp.isOpen:
				winComp.par.winclose.pulse()