# set base image (host OS)
FROM python:3.8-slim

# set the working directory in the container
WORKDIR /chorus

# copy the dependencies file to the working directory
COPY requirements.txt .

# Adding non-free to sources, because unrar is non-free
RUN echo "deb http://deb.debian.org/debian buster main non-free" > /etc/apt/sources.list; \
    echo "deb http://security.debian.org/debian-security buster/updates main non-free" >> /etc/apt/sources.list; \
    echo "deb http://deb.debian.org/debian buster-updates main non-free" >> /etc/apt/sources.list

# install dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y unrar unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY src/ .

# command to run on container start
CMD [ "python", "./bot.py" ]