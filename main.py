from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import (
    login_user,
    LoginManager,
    current_user,
    logout_user,
    login_required,
)
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from db_models import Posts, Users, Comments, db
from sqlalchemy.exc import SQLAlchemyError
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
ckeditor = CKEditor(app)
Bootstrap5(app)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["POSTGRES_DB_URI"]
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def user_loader(id):
    return db.get_or_404(Users, id)


def admin_privilages(func):
    def wrapper(post_id):
        if str(current_user.get_id()) == str(
            db.session.execute(
                db.select(Posts.author_id).where(Posts.id == post_id)
            ).scalar()
        ):
            return func(post_id)
        else:
            abort(403)

    wrapper.__name__ = func.__name__
    return wrapper


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        user = db.session.execute(
            db.select(Users).where(Users.email == form.email.data)
        ).scalar()
        if not form.validate_on_submit():
            return render_template("register.html", form=form)
        elif user:
            flash("Email already registered")
            return redirect(url_for("login"))
        else:
            temp_user = Users(
                name=form.name.data,
                email=form.email.data,
                password=generate_password_hash(
                    form.password.data, salt_length=16, method="pbkdf2:sha256"
                ),
            )
            try:
                db.session.add(temp_user)
                db.session.commit()
            except SQLAlchemyError as e:
                print(f"Error: {e.args}")
                abort(500)
            login_user(temp_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        user = db.session.execute(
            db.select(Users).where(Users.email == form.email.data)
        ).scalar()
        if not form.validate_on_submit():
            return render_template("login.html", form=form)
        elif not user:
            flash("User not found")
            return render_template("login.html", form=form)
        elif not check_password_hash(user.password, form.password.data):
            flash("Wrong password")
            return render_template("login.html", form=form)
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/")
def get_all_posts():
    result = db.session.execute(db.select(Posts))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(Posts, post_id)
    comments = list(
        db.session.execute(
            db.select(Comments).where(Comments.post_id == post_id)
        ).scalars()
    )
    user_names = [
        db.session.execute(
            db.select(Users.name).where(Users.id == comment.user_id)
        ).scalar()
        for comment in comments
    ]
    if request.method == "POST":
        temp_comment = Comments(
            body=form.comment.data, post_id=post_id, user_id=current_user.get_id()
        )
        try:
            db.session.add(temp_comment)
            db.session.commit()
        except SQLAlchemyError as e:
            print(f"Error: {e.args}")
            abort(500)
        return redirect(url_for("show_post", post_id=post_id))
    return render_template(
        "post.html",
        post=requested_post,
        comments=comments,
        form=form,
        usernames=user_names,
    )


@app.route("/new-post", methods=["GET", "POST"])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = Posts(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_name=current_user.name,
            date=date.today().strftime("%B %d, %Y"),
            author_id=current_user.get_id(),
        )
        try:
            db.session.add(new_post)
            db.session.commit()
        except SQLAlchemyError as e:
            print(f"Error: {e.args}")
            abort(500)
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_privilages
@login_required
def edit_post(post_id):
    post = db.get_or_404(Posts, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author_name=post.author_name,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author_name = current_user.name
        post.body = edit_form.body.data
        post.author_id = current_user.get_id()
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            print(f"Error: {e.args}")
            abort(500)
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_privilages
@login_required
def delete_post(post_id):
    post_to_delete = db.get_or_404(Posts, post_id)
    try:
        db.session.delete(post_to_delete)
        db.session.commit()
    except SQLAlchemyError as e:
        print(f"Error: {e.args}")
        abort(500)
    return redirect(url_for("get_all_posts"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
