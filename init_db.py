from wxcloudrun import app, db


def main():
    with app.app_context():
        db.create_all()
    print("Database tables created/updated successfully.")


if __name__ == "__main__":
    main()
