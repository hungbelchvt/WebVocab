from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from wtforms import PasswordField, SubmitField, StringField, TextAreaField, SelectField
from app.models import User

class RegistrationForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(message='Vui lòng nhập tên đăng nhập.'), Length(min=3, max=20, message='Tên đăng nhập phải từ 3 đến 20 ký tự.')])
    password = PasswordField('Mật khẩu', validators=[DataRequired(message='Vui lòng nhập mật khẩu.'), Length(min=6, message='Mật khẩu phải có ít nhất 6 ký tự.')])
    confirm_password = PasswordField('Xác nhận mật khẩu', validators=[DataRequired(message='Vui lòng xác nhận mật khẩu.'), EqualTo('password', message='Mật khẩu xác nhận không khớp.')])
    submit = SubmitField('Đăng ký tài khoản')

    # Check username
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Tên đăng nhập này đã được sử dụng. Vui lòng chọn tên khác.')

class LoginForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(message='Vui lòng nhập tên đăng nhập.')])
    password = PasswordField('Mật khẩu', validators=[DataRequired(message='Vui lòng nhập mật khẩu.')])
    submit = SubmitField('Đăng nhập')

class WordForm(FlaskForm):
    term = StringField('Từ vựng (Tiếng Anh)', validators=[DataRequired(message='Vui lòng nhập từ vựng.'), Length(max=100)])
    ipa = StringField('Phiên âm IPA (Tùy chọn)')
    definition = TextAreaField('Định nghĩa (Definition)', validators=[DataRequired(message='Vui lòng nhập định nghĩa.')])
    example_sentence = TextAreaField('Câu ví dụ (Example Sentence - Tùy chọn)')
    synonyms = StringField('Từ đồng nghĩa (Cách nhau bởi dấu phẩy, Tùy chọn)')
    topic_id = SelectField('Chủ đề', coerce=int, validators=[DataRequired(message='Vui lòng chọn chủ đề.')])
    submit = SubmitField('Lưu từ vựng')

class TopicForm(FlaskForm):
    name = StringField('Tên chủ đề', validators=[DataRequired(message='Vui lòng nhập tên chủ đề.'), Length(min=2, max=100, message='Tên chủ đề từ 2 đến 100 ký tự.')])
    submit = SubmitField('Tạo chủ đề')