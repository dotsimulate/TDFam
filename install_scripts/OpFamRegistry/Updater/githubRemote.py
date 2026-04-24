"""
GitHub Remote Extension for OpFamRegistry

Handles communication with the GitHub API to check for releases
and download updates.
"""

import re
import requests


class githubRemote:
	"""
	Handles GitHub API interactions for checking releases and downloading files.
	"""

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._log = None

	@property
	def log(self):
		"""Lazy-load logger to avoid issues during initialization."""
		if self._log is None:
			logger = self.ownerComp.op("logger")
			if logger and hasattr(logger, 'Log'):
				self._log = logger.Log
			else:
				self._log = lambda *args: debug(*args)
		return self._log

	def checkResponse(self, response: requests.Response):
		"""
		Validate and parse a requests Response object.

		Args:
			response: The requests Response object

		Returns:
			Parsed JSON data from response

		Raises:
			Exception: If response is not OK or empty
		"""
		if not response.ok:
			self.log("GitHub API error:", response.url, response.status_code, response.reason)
			raise Exception(f"GitHub API error: {response.status_code} {response.reason}")

		responseData = response.json()
		if not responseData:
			self.log("GitHub returned empty response!", response.url)
			raise Exception("Empty response from GitHub API")

		return responseData

	def getRepoData(self):
		"""
		Extract owner and repo name from the Repository parameter.

		Returns:
			list: [owner, repo_name]
		"""
		repo_url = self.ownerComp.par.Repository.eval()
		match = re.search(r"github\.com\/([\w,-]+)\/([\w,-]+).*", repo_url)
		if not match:
			raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
		return [str(value) for value in match.groups()]

	@property
	def fileRegex(self):
		"""Regex pattern to match release asset files."""
		return self.ownerComp.par.Fileregex.eval()

	def searchFile(self, releaseDict: dict):
		"""
		Search for a matching file in a release's assets.

		Args:
			releaseDict: GitHub release data dictionary

		Returns:
			str: Download URL for the matching asset

		Raises:
			Exception: If no matching file found
		"""
		assets = releaseDict.get("assets", [])
		for assetElement in assets:
			if re.match(self.fileRegex, assetElement["name"]):
				return assetElement["browser_download_url"]
		raise Exception(f"Could not find file matching regex: {self.fileRegex}")

	def getAndRaise(self, url):
		"""
		Make a GET request and raise on error.

		Args:
			url: URL to fetch

		Returns:
			requests.Response object
		"""
		response = requests.get(url.strip())
		response.raise_for_status()
		return response

	def fetchLatest(self):
		"""
		Fetch the download URL for the latest release.

		Returns:
			str: Download URL for the latest release asset
		"""
		owner, repoName = self.getRepoData()[0:2]
		apiEndpoint = f"https://api.github.com/repos/{owner}/{repoName}/releases/latest"
		response = self.getAndRaise(apiEndpoint)
		return self.searchFile(self.checkResponse(response))

	@property
	def tagRegex(self):
		"""Regex pattern to match release tags."""
		return self.ownerComp.par.Tagregex.eval()

	def fetchByTag(self):
		"""
		Fetch the download URL for a release matching the tag regex.

		Returns:
			str: Download URL for the matching release asset

		Raises:
			Exception: If no matching tag found
		"""
		owner, repoName = self.getRepoData()[0:2]
		search_depth = self.ownerComp.par.Searchdepth.eval()
		apiEndpoint = f"https://api.github.com/repos/{owner}/{repoName}/releases?per_page={search_depth}"
		response = self.getAndRaise(apiEndpoint)

		for releaseDict in self.checkResponse(response):
			if re.match(self.tagRegex, releaseDict["name"]):
				return self.searchFile(releaseDict)

		raise Exception(f"Could not find release matching tag regex: {self.tagRegex}")

	def FetchReleaseNotes(self):
		"""
		Fetch the release notes (body) for a release based on current Mode.

		Returns:
			str: Markdown release notes, or empty string if none
		"""
		owner, repoName = self.getRepoData()[0:2]
		mode = self.ownerComp.par.Mode.eval()

		if mode == "Latest":
			apiEndpoint = f"https://api.github.com/repos/{owner}/{repoName}/releases/latest"
			response = self.getAndRaise(apiEndpoint)
			return self.checkResponse(response).get("body", "") or ""

		if mode == "Search Tag":
			search_depth = self.ownerComp.par.Searchdepth.eval()
			apiEndpoint = f"https://api.github.com/repos/{owner}/{repoName}/releases?per_page={search_depth}"
			response = self.getAndRaise(apiEndpoint)
			for releaseDict in self.checkResponse(response):
				if re.match(self.tagRegex, releaseDict["name"]):
					return releaseDict.get("body", "") or ""
			raise Exception(f"Could not find release matching tag regex: {self.tagRegex}")

		raise Exception(f"Invalid Mode selected: {mode}")

	def ExternalData(self):
		"""
		Main entry point for fetching release data based on mode.

		Returns:
			str: Download URL for the release asset
		"""
		mode = self.ownerComp.par.Mode.eval()
		if mode == "Latest":
			return self.fetchLatest()
		if mode == "Search Tag":
			return self.fetchByTag()
		raise Exception(f"Invalid Mode selected: {mode}")

	def PollLatestTag(self):
		"""Trigger an async check for the latest release tag."""
		webclient = self.ownerComp.op('webclient1')
		if webclient:
			webclient.par.request.pulse()

	def OnCheckResponse(self, location):
		"""
		Callback when the tag check response is received.
		Extracts the tag from the redirect location and notifies the updater.

		Args:
			location: The redirect URL containing the tag
		"""
		tag = self._extract_github_tag(location)
		# Notify the parent Updater component
		if hasattr(parent, 'Updater') and hasattr(parent.Updater, 'OnPolledLatestTag'):
			parent.Updater.OnPolledLatestTag(tag)

	def _extract_github_tag(self, url):
		"""
		Extract the tag from a GitHub releases URL.

		Args:
			url: GitHub release URL (e.g., '.../releases/tag/v1.0.0')

		Returns:
			str or None: The tag if found, None otherwise
		"""
		if not url:
			return None
		pattern = r'/releases/tag/([^ ]+)$'
		match = re.search(pattern, url)
		return match.group(1) if match else None


