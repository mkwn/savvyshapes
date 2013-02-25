from google.appengine.api import users

from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

import urllib
import datetime
import re

class DataString(db.Model):
	data = db.TextProperty()

def getUOC(courseCode):
	year = datetime.datetime.now().year
	urls = ["http://www.handbook.unsw.edu.au/"+level+"graduate/courses/"+str(year)+"/"+courseCode+".html" for level in ["under","post"]]
	urls = urls[::1-2*(courseCode[4]>"4")]
	fetched = urlfetch.fetch(urls[0])
	if fetched.status_code == 404:
		fetched = urlfetch.fetch(urls[1])
		if fetched.status_code == 404:
			return None
	handbook = fetched.content
	try:
		return re.search(r"Units of Credit:.*(\d+)", handbook).group(1)
	except:
		return None

def getTable(courseCode, semester):
	#use http://www.cse.unsw.edu.au/~nss/sitar/classes2010 etc for past years
	faculty = courseCode[:4]
	url = "https://my.unsw.edu.au/classutil/"+faculty+"_"+semester+".html";
	rawtable = urlfetch.fetch(url).content
	try:
		rawtable = rawtable[rawtable.index('name="'+courseCode)+5:]
	except ValueError:
		return None
	try:
		rawtable = rawtable[:rawtable.index('name="'+faculty)]
	except ValueError:
		try:
			rawtable = rawtable[:rawtable.index("^ top ^")]
		except ValueError:
			return None
	table = re.findall(r"<tr(.*?)</tr>",'<tr'+rawtable.replace('\n',''));
	try:
		table[0] = re.search(r"valign=center>(.+?)</td>$", table[0]).group(1)
		return table
	except:
		return None	

def parseTable(table, ignoreFull, prefix):
	smartTable = {}
	errorData = ""
	openLectureTypes = []
	for row in table:
		try:
			classType = re.search(r'>([^>]*?)</td>', row).group(1)
		except:
			return None
		if not classType in smartTable:
			smartTable[classType] = []

		if classType[:2] == "LE":
			if "<td>Open</td>" in row:
				openLectureTypes += [classType]
		else:
			if not ignoreFull:
				if not "<td>Open</td>" in row:
					continue

		try:
			timedata = re.findall(r"<td>(.*?)</td>", row)[-1]
		except:
			return None
		timedata = re.sub(r"\(.*?\)","",timedata)
		timeslots = timedata.split(";")
		timeblocks = []		
		for timeslot in timeslots:
			#each slot is formatted as
			#Mon Tue 11-14
			days = re.findall(r"Mon|Tue|Wed|Thu|Fri", timeslot)
			try:
				timestring = re.search(r"\d\d(:30)?(-\d\d(:30)?)?", timeslot).group(0)
			except:
				return None
			blocktimes = []
			if '-' in timestring:
				endTime = timestring[timestring.index('-')+1:]
				for blocktime in range(int(timestring[:2]),int(endTime[:2])+(len(endTime)>3)):
					blocktimes += ["%02d" % blocktime]
			else:
				blocktimes = [timestring[:2]]
			timeblocks += [day+" "+blocktime for day in days for blocktime in blocktimes]
		timeblockData = ",".join(timeblocks)
		if not timeblockData in smartTable[classType]:
			smartTable[classType] += [timeblockData]
		
	courseData = ""
	for classType, classTimeData in smartTable.items():
		if classType[:2] == "LE" and not classType in openLectureTypes:
			errorData += "3"
		if len(classTimeData) == 0:
			errorData += "2"
		courseData += '-'+classType+'-' + '\n' + "/\n".join(classTimeData) + '\n'
	return errorData+prefix+courseData

class FetchPage(webapp.RequestHandler):
	def get(self):
		errorData = ""
		courseCode = self.request.get('courseCode');
		semester = self.request.get('semester');
		ignoreFull = False
		if self.request.get('ignoreFull'):
			ignoreFull = True
		UOC = getUOC(courseCode)
		if not UOC:
			UOC = "6"
			errorData += "0"
		table = getTable(courseCode, semester)
		if not table:
			return self.response.out.write("11@")
		courseName = table[0]
		table = table[1:]
		courseData = parseTable(table, ignoreFull, errorData+"@"+courseCode+" ["+courseName+"] ["+UOC+"]\n")
		if not courseData:
			return self.response.out.write("1@")
		self.response.out.write(courseData)
		
class MainPage(webapp.RequestHandler):
	def get(self):
		dataString = self.request.get('v')
		if dataString:
			DataStringInstance = DataString()
			DataStringInstance.data = dataString
			DataStringInstance.put()
			self.redirect(str(DataStringInstance.key().id()))
		else:
			self.response.out.write(template.render('index.htm',{}))

class ViewPage(webapp.RequestHandler):
	def get(self, id):
		dataString = DataString.get_by_id(int(id))
		self.response.out.write(template.render('view.htm',{"dataString":dataString.data,"id":id}))

application = webapp.WSGIApplication([
									('/', MainPage),
									('/(\d+)', ViewPage),
									('/fetch', FetchPage)])

def main():
	run_wsgi_app(application)

if __name__ == "__main__":
	main()
