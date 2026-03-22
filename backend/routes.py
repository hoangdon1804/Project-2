from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas
import auth

from database import SessionLocal

router = APIRouter()


def get_db():

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        hashed = auth.hash_password(user.password)

        new_user = models.User(
            username=user.username,
            password=hashed,
            role=user.role
        )

        db.add(new_user)
        db.commit()
        return {"msg": "created"}
    
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user:
        return {"error": "user not found"}

    if not auth.verify_password(user.password, db_user.password):
        return {"error": "wrong password"}

    token = auth.create_token({
        "id": db_user.id,
        "role": db_user.role
    })

    return {"token": token, "role": db_user.role}