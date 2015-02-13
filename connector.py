# -*- coding:utf-8 -*-

import tornado.ioloop as tioloop
import tornado.web as tweb

import xml.etree.ElementTree as et
import pony.orm as orm

import os
__dir__ = os.path.abspath(os.path.dirname(__file__))

def _field(func_name,*a,**ka):
	func = getattr(orm,func_name)
	# lazy function
	return lambda:func(*a,**ka)

class base_handler(tweb.RequestHandler):
	def write_xml(self,x):
		if isinstance(x,et.Element):
			x = et.tostring(x,encoding="utf-8")
		self.write(x)
		self.set_header("Content-Type","text/xml")

class grid_handler(base_handler):
	def initialize(self,*a,**ka):
		"""ka 必要参数：
		@db_name：数据库路径(str)
		@db_type：数据库类型(str)
		ka 可选参数：
		@table_name：指定table(str)
		@user_field：自定义的数据库字段
		@default_frame：grid默认xml路径(str)"""
		if ka.has_key("default_frame"):
			self.default_frame = ka['default_frame']
		if not ( ka.has_key("db_name") and ka.has_key("db_type") ):
			raise KeyError('Require db_name and db_type')
		# 
		self.db = orm.Database(ka['db_type'], ka['db_name'], create_db=True)
		attrs = dict(
			id = orm.PrimaryKey(int, auto=True))
		if ka.has_key("table_name"):
			attrs['_table_'] = ka['table_name']
		if ka.has_key("user_field"):
			self.user_field = ka['user_field'].keys()
			for k,v in ka['user_field'].items():
				# user_field()返回lazy函数，所以要v()
				attrs[k] = v()
		# 用元类的方法构造数据库model（http://developer.51cto.com/art/201108/281521.htm）
		self.Grid_model = type('Grid_model',(self.db.Entity,),attrs)
		self.db.generate_mapping(create_tables=True)

	def get(self):
		if hasattr(self,"default_frame"):
			rows = et.parse(self.default_frame).getroot()
		else:
			rows = et.Element('rows')
		with orm.db_session:
			for i in orm.select(c for c in self.Grid_model):
				row = et.Element("row")
				row.set("id",str(i.id))
				if hasattr(self,"user_field"):
					for _cell in self.user_field:
						cell = et.Element("cell")
						cell.text = getattr(i,_cell)
						row.append(cell)
				rows.append(row)
		self.write_xml(rows)
	def post(self):
		if self.get_argument("editing",default=None) != "true":
			return
		ids = self.get_body_argument("ids",default="").split(',')
		res = et.Element("data")
		for _id in ids:
			gr_id = self.get_body_argument("%s_gr_id" %(_id,))
			field = {}
			if hasattr(self,"user_field"):
				for _name in self.user_field:
					field[_name] = self.get_body_argument("%s_%s" %(_id,_name),default="-")
			status = self.get_body_argument("%s_!nativeeditor_status" %(_id,))
			# 写入数据库
			tid = [gr_id]
			with orm.db_session:
				if status=="updated":
					r = self.Grid_model[gr_id]
					for k,v in field.items():
						setattr(r,k,v)
				if status=="inserted":
					r = self.Grid_model(**field)
					# 提交以更新id
					orm.commit()
					tid[0] = str(r.id)
				if status=="deleted":
					r = self.Grid_model[gr_id]
					self.Grid_model[gr_id].delete()
			# 插入一条 action xml item
			act = et.Element("action")
			act.set("type",status)
			act.set("sid",gr_id)
			act.set("tid",tid[0])
			res.append(act)
		self.write_xml(res)