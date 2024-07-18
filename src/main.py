from typing import List
import dotenv
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from mangum import Mangum
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os
import secrets
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette_discord.client import DiscordOAuthClient
import datetime


load_dotenv()
CLIENT_ID = os.getenv("client-id")
CLIENT_SECRET = os.getenv("client-secret")
REDIRECT_URI = os.getenv("redirect-url")

app = FastAPI()
client = DiscordOAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
handler = Mangum(app)


@app.get("/login")
async def login_with_discord(request: Request):
    if not request.session.get("discord_user"):
        return client.redirect()
    return RedirectResponse("/dash")


# NOTE: REDIRECT_URI should be this path.
@app.get("/callback")
async def callback(request: Request, code: str):
    sesh = await client.login_return_token(code)
    user_json = sesh[0].json()
    user_json["token"] = sesh[1]
    user_json["current_time"] = str(datetime.datetime.utcnow())
    request.session["discord_user"] = user_json

    return RedirectResponse("/home")

@app.get("/new_token")
async def new_token(request: Request,refresh_token: str):
    user = request.session.get("discord_user")
    if not user:
        return {"status": "error", "message": "User not logged in"}
    if refresh_token == request.session.get("discord_user")["token"]["refresh_token"]:
        sesh = client.session_from_token(user["token"])
        new_token = await sesh.refresh()
        user = await sesh.identify()
        user_json = user.json()
        user_json["token"] = new_token
        user_json["current_time"] = str(datetime.datetime.utcnow())
        request.session["discord_user"] = user_json
        return {"status": "success"}


@app.get("/home")
async def dash(request: Request):
    # redirects to the login page if the user is not logged in
    if not request.session.get("discord_user"):
        return RedirectResponse("/login")
    user = request.session.get("discord_user")
    user_token = user["token"]

    if datetime.datetime.utcnow() > datetime.datetime.fromtimestamp(float(user_token["expires_at"])):
        await new_token(request,user_token["refresh_token"])
        user = request.session.get("discord_user")
        user_token = user.json()["token"]
    
    sesh = client.session_from_token(user_token)
    user = await sesh.identify()
    user_json = user.json()
    user_json["token"] = user_token
    user_json["current_time"] = str(datetime.datetime.utcnow())
    request.session["discord_user"] = user_json
    return templates.TemplateResponse("chat.html",{"request":request,"avatar":f"https://cdn.discordapp.com/avatars/{user.id}/{user.avatar}.png","user_name":user_json["global_name"],"uid":user.id,"banner_color":user.banner_color})


app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(64))

