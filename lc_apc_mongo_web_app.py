from flask import Flask
from flask_pymongo import PyMongo


app = Flask(__name__)
app.config['DEBUG'] = True
app.config['MONGO_URI'] = 'mongodb://localhost/apcdata'
mongo = PyMongo(app)


@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/dept/<ObjectId:dept_id>')
def dept(dept_id):
    dept = mongo.db.depts.find_one({'_id': dept_id})
    return "name: {0} division: {1} abbrev: {2} id: {3}".format(dept['name'],dept['division'],dept['abbrev'], dept['_id'])


if __name__ == '__main__':
    app.run()
