# set base image (host OS)
FROM python:3.8-alpine

# set the working directory in the container
WORKDIR /chorus

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN apk update && apk --update add --no-cache --virtual \ 
    .build-deps gcc musl-dev \
    unzip \
    unrar 
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY src/ .

# command to run on container start
CMD [ "python", "./bot.py" ]