FROM continuumio/miniconda3:latest
MAINTAINER Mingxun Wang "mwang87@gmail.com"

RUN conda install -c conda-forge dash
RUN conda install -c anaconda pandas
RUN conda install -c anaconda flask
RUN conda install -c anaconda gunicorn
RUN conda install -c anaconda requests
RUN conda install -c conda-forge dash-bootstrap-components

COPY . /app
WORKDIR /app

