from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField, DateField
from wtforms.validators import DataRequired, Optional

class DuesCreateForm(FlaskForm):
    member_id = SelectField('Member', coerce=int, validators=[DataRequired()])
    dues_type_id = SelectField('Dues Type', coerce=int, validators=[DataRequired()])
    dues_amount = FloatField('Dues Amount', validators=[DataRequired()])
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Create Dues Record')

class DuesPaymentForm(FlaskForm):
    amount_paid = FloatField('Amount Paid', validators=[DataRequired()])
    document_number = StringField('Document Number', validators=[Optional()])
    payment_received_date = DateField('Payment Received Date', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Record Payment')

class DuesUpdateForm(FlaskForm):
    dues_amount = FloatField('Dues Amount', validators=[DataRequired()])
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Update Dues Record')
