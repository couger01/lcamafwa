from flask import Flask,render_template, abort, request, redirect, url_for, current_app,session, flash, get_flashed_messages
from flask_pymongo import PyMongo
from jinja2 import TemplateNotFound
from flask_wtf import FlaskForm
from wtforms import StringField, SelectMultipleField, SubmitField, TextAreaField, IntegerField, DateTimeField, RadioField
from wtforms.validators import DataRequired
from flask_wtf.csrf import CSRFProtect
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager, login_user, UserMixin, current_user, logout_user, login_required
from flask_ldap3_login.forms import LDAPLoginForm
from flask.ext.principal import Principal, Identity, AnonymousIdentity, \
     identity_changed, identity_loaded, UserNeed, RoleNeed

class UserForm(FlaskForm):
    dept = SelectMultipleField('Departments',choices=[])
    chair = SelectMultipleField('Chairs',choices=[])
    edit = SubmitField('Edit')

    def __init__(self, *args, **kwargs):
        self.dept.kwargs['choices'] = [(item['abbrev'], item['name']) for item in mongo.db.depts.find()]
        self.chair.kwargs['choices'] = [('APC','APC')]
        self.chair.kwargs['choices'].extend([(item['abbrev'], item['name']) for item in mongo.db.depts.find()])
        self.chair.kwargs['choices'].extend([(item, item) for item in mongo.db.depts.find().distinct('division')])
        FlaskForm.__init__(self, *args, **kwargs)

class CourseForm(FlaskForm):
    title = StringField('Title')
    number = StringField('Number')
    credit_hrs = StringField('Credit Hours')
    capacity = StringField('Capacity')
    gen_ed = SelectMultipleField('Gen Eds',choices=[])
    desc = TextAreaField('Description')
    dept = SelectMultipleField('Departments',choices=[])
    edit = SubmitField('Edit')

    def __init__(self,*args, **kwargs):
        self.gen_ed.kwargs['choices']= [(item['name'],item['title']) for item in mongo.db['geneds'].find()]
        self.dept.kwargs['choices'] = [(item['abbrev'], item['name']) for item in mongo.db.depts.find()]
        FlaskForm.__init__(self, *args, **kwargs)

class ProposalForm(FlaskForm):
    owner = StringField('Owner')
    stage = IntegerField('Stage')
    staffing = TextAreaField('Staffing')
    rationale = TextAreaField('Rationale')
    impact = TextAreaField('Impact')
    date = DateTimeField('Date')
    action = RadioField('Action',choices=[('null','None'),('DEL','delete')])
    fees = TextAreaField('Fees')
    est_enrollment = IntegerField('Estimated Enrollment')
    instructors = SelectMultipleField('Instructors',choices=[])
    terms = SelectMultipleField('Terms',choices=[()])
    edit = SubmitField("edit")

    def __init__(self,*args, **kwargs):
        self.instructors.kwargs['choices']= [(item['name'],item['name']) for item in mongo.db['users'].find()]
        self.terms.kwargs['choices'] = [(item, item) for item in ['FALL', 'SPRING', 'J_TERM', 'SUMMER SESSION I', 'SUMMER SESSION II']]
        FlaskForm.__init__(self, *args, **kwargs)

class DepartmentForm(FlaskForm):
    name = StringField("Name")
    abbrev = StringField("Abbreviation")
    division = StringField("Division")
    edit = SubmitField("Edit")

class GerForm(FlaskForm):
    title = StringField("title")
    effective = DateTimeField("Beginning Date")
    end = DateTimeField("End date")
    edit = SubmitField("Edit")

class CalendarForm(FlaskForm):
    pass


app = Flask(__name__)
app.config['DEBUG'] = True
app.config['MONGO_URI'] = 'mongodb://localhost/apcdata'
app.config['SECRET_KEY'] = 'oqbe5vgm(&y)xjsuph$zx*-z8(3wp84a2#wlo%bqsipd-g%y#x'
app.config['LDAP_HOST'] = 'localhost'

# Base DN of your directory
app.config['LDAP_BASE_DN'] = 'dc=apcdev,dc=com'

# Users DN to be prepended to the Base DN
app.config['LDAP_USER_DN'] = 'ou=users'

# Groups DN to be prepended to the Base DN
app.config['LDAP_GROUP_DN'] = 'ou=groups'

# The RDN attribute for your user schema on LDAP
app.config['LDAP_USER_RDN_ATTR'] = 'uid'

# The Attribute you want users to authenticate to LDAP with.
app.config['LDAP_USER_LOGIN_ATTR'] = 'mail'

# The Username to bind to LDAP with
app.config['LDAP_BIND_USER_DN'] = None

app.config['LDAP_GROUP_OBJECT_FILTER'] = '(objectclass=groupOfNames)'

# The Password to bind to LDAP with
app.config['LDAP_BIND_USER_PASSWORD'] = None
app.config['LDAP_PORT'] = 10389
app.config['LDAP_HOST'] = 'localhost'
mongo = PyMongo(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)              # Setup a Flask-Login Manager
ldap_manager = LDAP3LoginManager(app)          # Setup a LDAP3 Login Manager.
Principal(app)

# Create a dictionary to store the users in when they authenticate
# This example stores users in memory.
ldap_users = {}

# Declare an Object Model for the user, and make it comply with the
# flask-login UserMixin mixin.
class User(UserMixin):
    def __init__(self, dn, username, data):
        self.dn = dn
        self.username = username
        self.data = data

    def __repr__(self):
        return self.dn

    def get_id(self):
        return self.dn

# Declare a User Loader for Flask-Login.
# Simply returns the User if it exists in our 'database', otherwise
# returns None.
@login_manager.user_loader
def load_user(id):
    if id in users:
        return ldap_users[id]
    return None


# Declare The User Saver for Flask-Ldap3-Login
# This method is called whenever a LDAPLoginForm() successfully validates.
# Here you have to save the user, and return it so it can be used in the
# login controller.
@ldap_manager.save_user
def save_user(dn, username, data, memberships):
    user = User(dn, username, data)
    ldap_users[dn] = user
    return user

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    if hasattr(current_user, 'dn'):
        identity.provides.add(UserNeed(current_user.get_id))

    # Assuming the User model has a list of roles, update the
    # identity with the roles that the user provides
    if hasattr(current_user, 'memberships'):
        for role in current_user.memberships:
            identity.provides.add(RoleNeed(role.name))


@app.route('/')
def index():
    try:
        return render_template('index.html')
    except TemplateNotFound:
        abort(404)

@app.route('/login', methods=['GET', 'POST'])
def login():

    # Instantiate a LDAPLoginForm which has a validator to check if the user
    # exists in LDAP.
    form = LDAPLoginForm()

    if form.validate_on_submit():
        # Successfully logged in, We can now access the saved user object
        # via form.user.
        login_user(form.user)  # Tell flask-login to log them in.
        identity_changed.send(current_app._get_current_object(),identity=Identity(form.user.get_id))
        return redirect(url_for('index'))  # Send them home

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    # Remove the user information from the session
    logout_user()

    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())

    return redirect(url_for('index'))


@app.route('/about')
def about():
    try:
        return render_template('about.html')
    except TemplateNotFound:
        abort(404)

@app.route('/users/')
def users():
    users = mongo.db.users.find({})
    try:
        return render_template('users.html',users=users)
    except TemplateNotFound:
        abort(404)

@app.route('/users/user/<ObjectId:user_id>')
def user(user_id):
    user = mongo.db.users.find_one({'_id': user_id})
    try:
        return render_template('user.html',user=user,form=UserForm(dept=[item for item in user['dept']],chair=[c for c in user['chairs']]))
    except TemplateNotFound:
        abort(404)

@app.route('/users/user/<ObjectId:user_id>/edit',methods=['POST'])
def user_edit(user_id):
    user = mongo.db.users.find_one({'_id': user_id})
    form = UserForm(request.form)
    if request.method == 'POST':
        mongo.db.users.find_one_and_update({'_id': user['_id']},{'$set':{'dept': [item for item in form.dept.data],'chairs': [item for item in form.chair.data]}})
        return redirect(url_for('user',user_id=user['_id']))

@app.route('/courses/')
def courses():
    courses = mongo.db.courses.find({})
    try:
        return render_template('courses.html',courses=courses,form=CourseForm())
    except TemplateNotFound:
        abort(404)

@app.route('/courses/course/<ObjectId:course_id>')
def course(course_id):
    course = mongo.db.courses.find_one({'_id': course_id})
    try:
        return render_template('course.html',course=course,form=CourseForm(title=course['title'],number=course['name'].split('-')[1],credit_hrs=course['credit_hrs'],capacity=course['capacity'],gen_ed=[item for item in (course['gen_eds'] if course['gen_eds'] is not None else [])],desc=course['desc'],dept=course['dept']))
    except TemplateNotFound:
        abort(404)

@app.route('/courses/course/<ObjectId:course_id>/edit',methods=['POST'])
def course_edit(course_id):
    course = mongo.db.courses.find_one({'_id': course_id})
    form = CourseForm(request.form)
    if request.method == "POST":
        mongo.db.courses.find_one_and_update({'_id': course['_id']},{'$set':{'title':form.title.data,'name':form.dept.data[0] + '-' + form.number.data,'credit_hrs':form.credit_hrs.data,'capacity':form.capacity.data,'gen_eds':[item for item in form.gen_ed.data],'desc':form.desc.data}})
        return redirect(url_for('course', course_id=course['_id']))

@app.route('/courses/course/new',methods=['POST'])
def course_new():
    form = CourseForm(request.form)
    course = {'title':form.title.data,'name':form.dept.data[0] + '-' + form.number.data,'credit_hrs':form.credit_hrs.data,'capacity':form.capacity.data,'gen_eds':[item for item in form.gen_ed.data],'desc':form.desc.data}
    if request.method == "POST":
        mongo.db.courses.insert_one(course)
        return redirect(url_for('courses'))

@app.route('/proposals/')
def proposals():
    proposals = mongo.db.proposals.find({})
    try:
        return render_template('proposals.html',proposals=proposals)
    except TemplateNotFound:
        abort(404)

@app.route('/proposals/proposal/<ObjectId:proposal_id>')
def proposal(proposal_id):
    proposal = mongo.db.proposals.find_one({'_id': proposal_id})
    try:
        return render_template('proposal.html',proposal=proposal,form=ProposalForm())
    except TemplateNotFound:
        abort(404)

@app.route('/proposals/proposal/<ObjectId:proposal_id>/edit',methods=['POST'])
def proposal_edit(proposal_id):
    flash("Editing a proposal is not implemented yet.",'warning')
    return redirect(url_for('proposal',proposal_id=proposal_id))


@app.route('/departments/')
def depts():
    depts = mongo.db.depts.find({})
    try:
        return render_template('departments.html',depts=depts)
    except TemplateNotFound:
        abort(404)

@app.route('/departments/dept/<ObjectId:dept_id>')
def dept(dept_id):
    dept = mongo.db.depts.find_one({'_id': dept_id})
    try:
        return render_template('department.html',dept=dept)
    except TemplateNotFound:
        abort(404)

@app.route('/departments/dept/<ObjectId:dept_id>/edit')
def dept_edit(dept_id):
    flash("Editing a department is not implemented yet.", 'warning')
    return redirect(url_for('depts', dept_id=dept_id))

@app.route('/departments/dept/new')
def dept_new():
    flash("Adding a new department is not implemented yet.", 'warning')
    return redirect(url_for('depts'))

@app.route('/general-education-requirements/')
def gers():
    gers = mongo.db['geneds'].find({})
    try:
        return render_template('gers.html',gers=gers)
    except TemplateNotFound:
        abort(404)

@app.route('/general-education-requirements/general-education-requirement/<ObjectId:ger_id>')
def ger(ger_id):
    ger = mongo.db['geneds'].find_one({'_id':ger_id})
    try:
        return render_template('ger.html',ger=ger)
    except TemplateNotFound:
        abort(404)

@app.route('/general-education-requirements/general-education-requirement/<ObjectId:ger_id>/edit')
def ger_edit(ger_id):
    flash("Editing a general education requirement is not implemented yet.", 'warning')
    return redirect(url_for('ger', ger_id=ger_id))

@app.route('/general-education-requirements/general-education-requirement/new')
def ger_new():
    flash("Adding a new general education requirement is not implemented yet.", 'warning')
    return redirect(url_for('gers'))

@app.route('/calendar-events/')
def calendar_events():
    calendar_events = mongo.db['calendar-events'].find({})
    try:
        return render_template('calendar_events.html',calendar_events=calendar_events)
    except TemplateNotFound:
        abort(404)

@app.route('/calendar-events/calendar-event/<ObjectId:calendar_event_id>')
def calendar_event(calendar_event_id):
    calendar_event = mongo.db['calendar-events'].find_one({'_id':calendar_event_id})
    try:
        return render_template('calendar_event.html',calendar_event=calendar_event)
    except TemplateNotFound:
        abort(404)

@app.route('/calendar-events/calendar-event/<ObjectId:calendar_event_id>/edit')
def calendar_event_edit(calendar_event_id):
    flash("Editing a calendar event is not implemented yet.",'warning')
    return redirect(url_for('calendar_event',calendar_event_id=calendar_event_id))

@app.route('/calendar-events/calendar-event/new')
def calendar_event_new():
    flash("Adding a new calendar event is not implemented yet.",'warning')
    return redirect(url_for('calendar_events'))



if __name__ == '__main__':
    app.run()
