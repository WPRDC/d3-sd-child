import json
import math
import operator
import requests
import time
import cStringIO
import gzip
import boto
import boto.s3.connection

from collections import OrderedDict
from django.conf import settings
from django.utils import simplejson
from .utils import get_ratio, get_division, SUMMARY_LEVEL_DICT
from .models import Dashboards

from boto.s3.connection import S3Connection, Location
from boto.s3.key import Key

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)

class ApiClient(object):
	def __init__(self, base_url):
		self.base_url = base_url

	def _get(self, path, params=None):
		url = self.base_url + path
		# print url
		# print params
		r = requests.get(url, params=params)
		data = None
		# print r
		time.sleep(1)
		if r.status_code == 200:
			data = r.json(object_pairs_hook=OrderedDict)
		else:
			raise Exception("Error fetching data: " + r.json().get("error"))

		return data

	def get_parent_geoids(self, geoid):
		return self._get('/1.0/geo/tiger2017/{}/parents'.format(geoid))

	def get_geoid_data(self, geoid):
		return self._get('/1.0/geo/tiger2017/{}'.format(geoid))

	def get_data(self, table_ids, geo_ids, acs='latest'):
		if hasattr(table_ids, '__iter__'):
			table_ids = ','.join(table_ids)

		if hasattr(geo_ids, '__iter__'):
			geo_ids = ','.join(geo_ids)

		return self._get('/1.0/data/show/{}'.format(acs), params=dict(table_ids=table_ids, geo_ids=geo_ids))


def custom_s3_keyname(geo_id):
	return '/1.0/data/profiles/%s.json' % geo_id.upper()

def custom_make_s3():
	if settings.AWS_KEY and settings.AWS_SECRET:
		custom_s3 = boto.s3.connect_to_region('us-east-2', aws_access_key_id=settings.AWS_KEY,aws_secret_access_key=settings.AWS_SECRET, calling_format = boto.s3.connection.OrdinaryCallingFormat(),)
		logger.warn(custom_s3)
		custom_lookup = custom_s3.lookup('d3-sd-child')
	else:
		try:
			custom_s3 = S3Connection()
		except:
			custom_s3 = None
	return custom_s3

def custom_s3_profile_key(geo_id):
	custom_s3 = custom_make_s3()
	custom_key = None
	if custom_s3:  
		custom_bucket = custom_s3.get_bucket('d3-sd-child')
		custom_keyname = custom_s3_keyname(geo_id)
		custom_key = Key(custom_bucket, custom_keyname)
	
	return custom_key

def get_data(geo_id):
	
	try:
		custom_s3_key = custom_s3_profile_key(geo_id)
	except:
		custom_s3_key = None

	if custom_s3_key and custom_s3_key.exists():
		memfile = cStringIO.StringIO()
		custom_s3_key.get_file(memfile)
		memfile.seek(0)
		compressed = gzip.GzipFile(fileobj=memfile)

		# Read the decompressed JSON from S3
		profile_data_json = compressed.read()
		# Load it into a Python dict for the template
		profile_data = simplejson.loads(profile_data_json)
	else:
		profile_data = None


	return profile_data

def process_sub_categories(key, data, numerator):
	if (key == 'index') or (key == 'numerators'):
		# straight average
		if (data['this'] is None):
			data['custom'] = None
		else: 
			try:
				data['custom'] = float(data['this']) + data['custom']
			except KeyError as e:
				data['custom'] = float(data['this'])	

	elif (key == 'values') or (key == 'error') or (key == 'numerator_errors') or (key == 'error_ratio'):
		#weighted average
		if (data['this'] is None) or (numerator is None):
			data['custom'] = None
		else: 
			try:
				data['custom'] = (float(data['this']) * float(numerator)) + data['custom']
			except KeyError as e:
				data['custom'] = (float(data['this']) * float(numerator))

def normalize_sub_categories(key, data, numerator_total):
	if (key == 'index') or (key == 'numerators'):
		# straight average
		if (data['custom'] is None):
			data['this'] = None
		else: 
			data['this'] = data['custom']

	elif (key == 'values') or (key == 'error') or (key == 'numerator_errors') or (key == 'error_ratio'):
		#weighted average
		if (data['custom'] is None):
			data['this'] = None
		else: 
			data['this'] = data['custom'] / numerator_total

def create_custom_profile(slug):
	# look up geoids in database
	dashboard = Dashboards.objects.get(dashboard_slug=slug)
	geoids = dashboard.dashboard_geoids.split(",")

	doc = OrderedDict([('geography', OrderedDict()),
					   ('demographics', dict()),
					   ('economics', dict()),
					   ('families', dict()),
					   ('housing', dict()),
					   ('social', dict()),])

	#set up for geographies
	doc['geography']['this'] = dict()
	doc['geography']['this']['number_of_geographies'] = 0
	doc['geography']['this']['total_population'] = 0
	doc['geography']['this']['land_area'] = 0
	doc['geography']['this']['full_geoids'] = []
	doc['geo_metadata'] = dict()

	for i, geo_id in enumerate(geoids):
		profile_data = get_data(geo_id)

		# if the first time through the loop, copy the data over, then we'll overwrite the ['this'] dictionaries as we itterate  
		if i == 0:
			#custom geo metadata
			doc['geography']['census_release'] = profile_data['geography']['census_release']
			doc['geography']['census_release_year'] = profile_data['geography']['census_release_year']
			doc['geography']['census_release_level'] = profile_data['geography']['census_release_level']
			doc['geography']['this']['sumlevel_name'] = profile_data['geography']['this']['sumlevel_name']
			doc['geography']['this']['short_name'] = dashboard.dashboard_name
			doc['geography']['this']['sumlevel'] = profile_data['geography']['this']['sumlevel']
			doc['geography']['this']['short_geoid'] = None
			doc['geography']['this']['full_name'] = dashboard.dashboard_name

			# parents
			doc['geography']['parents'] = profile_data['geography']['parents']

			#copy the data
			doc['demographics'] = profile_data['demographics']
			doc['economics'] = profile_data['economics']
			doc['families'] = profile_data['families']
			doc['housing'] = profile_data['housing']
			doc['social'] = profile_data['social']

		#custom geo metadata
		doc['geography']['this']['number_of_geographies'] += 1
		doc['geography']['this']['land_area'] = profile_data['geography']['this']['land_area'] + doc['geography']['this']['land_area']
		doc['geography']['this']['full_geoids'].append(geo_id)
		doc['geography']['this']['total_population'] = profile_data['geography']['this']['total_population'] + doc['geography']['this']['total_population']

		#### demographics calculations ####

		# iterate thorough all values and create averages and weighted averages
		for top_level, top_level_data in doc.iteritems():
			if top_level != 'geography':
				for category, category_data in top_level_data.iteritems():
					for sub_category, sub_category_data in category_data.iteritems():
						if sub_category != 'metadata':
							try:
								numerator = sub_category_data['numerators']['this']
							except KeyError as e:
								pass

							for key, data in sub_category_data.iteritems():
								try:
									process_sub_categories(key, data, numerator)
								except KeyError as e:
									numerator = data['numerators']['this']
									# data is one more rung down the ladder
									for sub_key, sub_data in data.iteritems():
										process_sub_categories(sub_key, sub_data, numerator)
	

													
	# normalize 'custom' fields and set them to equal this
	for top_level, top_level_data in doc.iteritems():
		print top_level
		if top_level != 'geography':
			for category, category_data in top_level_data.iteritems():
				print category
				for sub_category, sub_category_data in category_data.iteritems():
					print sub_category
					if sub_category != 'metadata':
						try:
							numerator = sub_category_data['numerators']['custom']
						except KeyError as e:
							pass

						for key, data in sub_category_data.iteritems():
							print key
							try:
								normalize_sub_categories(key, data, numerator)
							except KeyError as e:
								numerator = data['numerators']['custom']
								# data is one more rung down the ladder
								for sub_key, sub_data in data.iteritems():
									normalize_sub_categories(sub_key, sub_data, numerator)
									
								

			
			
		









	square_miles = get_division(doc['geography']['this']['land_area'], 2589988)
	if square_miles < .1:
		square_miles = get_division(doc['geography']['this']['land_area'], 2589988, 3)
	total_pop = doc['geography']['this']['total_population']
	population_density = get_division(total_pop, get_division(doc['geography']['this']['land_area'], 2589988, -1))
	doc['geo_metadata']['square_miles'] = square_miles
	doc['geo_metadata']['population_density'] = population_density

	return doc

