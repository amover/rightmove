import re
import urllib
import urllib2
from BeautifulSoup import BeautifulSoup
import string
import datetime
import time
import logging
from urllib import urlencode
import pandas as pd
import mechanize
import numexpr
import sys


if 'logger' not in dir():
    # set up logging
    # create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    #~ formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    #~ ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)



#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

#~ Constants to navigate rightmove website:
c_pageOfNumPagesOnSearchResults = ['span',{'class':'pagenavigation pagecount'}] # used in find
#~ c_numPages = '\d+' #used in re.compile

#~ Trying to find:
    #~ <li class="regular clearfix  pos-5 summary-list-item" id="summary47764264" name="summary-list-item">
c_summary = ['li', {'id':re.compile('(?<=summary)\d{6,}')}]


class RMsearch():
    def __init__(self, filename='properties.csv'):
        # Create a browser
        self.br = mechanize.Browser()
        self.user_agent = 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0'
        self.br.addheaders = [('User-agent', self.user_agent)] 
        
        # Used for record access times
        self.today = str(time.gmtime()[:3] )
        
        self.database = filename
        
        try:
        #Initialize from file
            self.table = pd.DataFrame.from_csv(self.database)
            self.columns = self.table.columns
        except IOError:
            # Otherwise create from scratch
            self.columns = "id, price, postcode, adate, cdate, address, type, bedrooms, img, summary, coordinates, detail, agent_detail".replace(" ","").split(',')
            self.table = pd.DataFrame(columns=self.columns)
        
    def save(self, filename='properties.csv'):
        """Saves the database to file"""
        return self.table.to_csv(filename, encoding='utf-8')

    def makeSearchURL(self, **args):
        """Definition of full query fields here.  Copy this from Firefox debug form.
        
        Any argument accepted by righmove search can be passed here.
        
        Parsed into fields to save time"""
        
        rmQueryString = \
        """
        searchType=SALE
        locationIdentifier=
        previousSearchLocation=
        useLocationIdentifier=false
        searchLocation= 
        savedSearchId=
        radius=0.0
        displayPropertyType=
        minBedrooms=
        maxBedrooms=
        minPrice=
        maxPrice=
        maxDaysSinceAdded=
        _includeSSTC=on
        primaryDisplayPropertyType=
        secondaryDisplayPropertyType=
        oldDisplayPropertyType=
        oldPrimaryDisplayPropertyType=
        newHome=
        auction=false
        retirement=
        partBuyPartRent=
        businessForSale=
        sortByPriceDescending=
        sortType=
        viewType=
        numberOfPropertiesPerPage=10
        lastPersistLocId="""
        rmQuery = [[y for y in x.strip().split('=')] for x in rmQueryString.split('\n')]
        rmQuery = {k[0]: k[1] for k in rmQuery if len(k) == 2} # only load fields with values
        rmQuery.update(args) # any specific arguments passed, e.g. radius override, etc
        return rmQuery        
    
    def search(self, postcode, **args):
        """Perfoms a rightmove search
        
        postcode: can either be the postcode or any search term accepted by rightmove without confirmation, e.g. "Old Town, Swindon" also works.
            Acceptable search terms can be tried on the sidebar of an existing rightmove search (for some reason not from the main page).
            If the term is ambiguous, rightmove asks for confirmation.  This is not handled and will break the search.
            
        Any other rightmove search criteria can be passed, e.g minPrice, maxBedrooms, etc.  Have a look at the search form for ideas"""
        
        url = "http://www.rightmove.co.uk/property-for-sale/search.html?" + \
            urlencode(self.makeSearchURL(searchLocation=postcode))       
        response = self.br.open(url)
        splashSoup = BeautifulSoup(response.read())
        splashSoup.find('input',attrs={'type':'submit','value':'Find Properties'})
        numPages = self.soupSearchText(splashSoup, c_pageOfNumPagesOnSearchResults)[0].text
        if numPages == None:
            return
            
        numPages = int(re.findall('\d+',numPages)[-1])
    
        #~ pagesToBeProcessed = buildPageList(url, numPages)

        pagesToBeProcessed = [ "%s&index=%s0" % (url,x) for x in range(numPages)]   

        propertiesReady = []

        #Loop through the results pages
        for pageURL in pagesToBeProcessed:
            
                #~ print ".",
            sys.stdout.flush()
            #time.sleep(random.randint(30-120))
            
            # Get the content of this results page (this includes the zero-th)
            try:
                response = self.br.open(pageURL)
                soup = BeautifulSoup(response.read())
            #~ except BeautifulSoup.HTMLParser.HTMLParseError, e:
            except ValueError, e:
                print e
            
            #Loop through the property links
            #~ propertyIds = getPropertyLinks(soup)
            propertyIds = [x['id'] for x in self.soupSearchText(soup, c_summary)]
            propertyIds = [int(x.strip('summary')) for x in propertyIds]
            #~ logger.info("Found %d properties" % len(propertyIds))
            
            self.parseSummary(soup,postcode) 
    
    def parseSummary(self, page, postcode):
        regExPattern = re.compile('summary\d*')
        
        # Get the ordered list of properties from the page
        #~ resultSet = soup.find('ol', attrs={'id':'summaries'})
        results = page.findAll('li', attrs={'id':regExPattern})

        #~ self.table.set_index(['id','price'],inplace=True)
        ids = []
        for result in results:
            id = int(result['id'].lstrip('summary'))
            ids.append(id)
            adate = self.today
            try:
                price = int("0"+"".join([x for x in result.find('div', attrs={'class':'price-new'}).text if x in '0123456789']))
                address = result.find('span', attrs={'class':'displayaddress'})
                if address:
                    address = address.text
                type = result.find(attrs={'class':'address bedrooms'}).findAll('span')[0].text
                bedrooms = int("0"+"".join(re.findall('\d+',type)))
                summary = result.find('p', attrs={'class':'description'}).text
                img = result.find('img').get('src') 
                cdate = adate
                agent_detail = result.find('p', attrs={'class':'branchblurb'}).text
                #~ pdate_added = result.find('p',attrs={'class'='
            except TypeError:
                logger.info( "FAILED :"+str(id))
                continue
            #~"id, price, postcode, adate, cdate, address, type, bedrooms, img, summary, coordinates, detail"   
            #~ date repeated for access & creation dates
            prop = dict([(k,eval(k)) for k in self.columns if k in dir()])
            
            
            curr = self.table.query('id == @id')
            if price in curr.price.values:
                self.table.loc[self.table.id == id, 'adate'] = str(adate) #reset access date for all to today if record (id, price) exists
                #~ print "Duplicate id: ", id
                #~ self.table.loc[(pid,pprice)] = prop[2:] #update record, excluding 2 index fields
                pass
            else:
                new_prop = pd.DataFrame(prop,index=[id])
                if len(curr)>0:
                    logger.info("Change:%s in %s for price %d: %d bedrooms. Previously at:"%(type,postcode,price,bedrooms)+",".join([str(x) for x in curr.price.values]))
                else:
                    logger.info("New:%s in %s for price %d: %d bedrooms"%(type,postcode,price,bedrooms))
                #~ new_prop.set_index(['id','price'],inplace=True)
                self.table = pd.concat([self.table,new_prop])
            #~ self.table.loc[(id,pprice),:] =a pd.Series(prop[2:])
        #~ self.table.reset_index(inplace=True)
        return True
        
    def describe(self):
            # all items with prices changed today
            pd.options.display.max_rows = 200
            res={}
            t = self.table
            now = str(self.today)
            # all items with a price change
            price_change = [len(t.loc[t.id == x])>1 for x in t.id]
            # with an update day of today
            print "Price changes today"
            res['change']=( self.table.eval('cdate == @now').loc[price_change])
            print res['change']
            print "="*30
            
            ct = t.query('cdate == @now')
            print "New properties today:", len(ct)
            res['new']=ct.price.describe()
            print res['new']
            print "="*30+"\n"
            
            res['all']=ct.groupby(['postcode','bedrooms']).price.describe().unstack('postcode')
            print res['all']
            print "="*30+"\n"
            
            res['newdetail']=ct[['address','price','detail']]
            print res['newdetail']
            print "="*30+"\n"
            return res
            
    def soupSearchText(self, soup, search):
        """Takes a soup object and search using find taking with terms passed in search
            in the form:
                tag=search[0] and 
                attrs=search[1]
                
            Returns result.text if found, alternatively None"""
        if len(search)==1:
            res = soup.findAll(search[0])
        elif len(search)==2:
            res = soup.findAll(search[0], attrs=search[1])
            
        if res:
            return res
        else:
            return None
    
    def updateAll(self):
        for c in self.table.postcode.unique():
            self.search(c)
            


r=RMsearch()
#~ r.search('MK11')
#~ a=r.describe()
r.updateAll()
r.save()
#~ r.save()
