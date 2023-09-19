FROM continuumio/miniconda3:4.10.3
MAINTAINER Mingxun Wang "mwang87@gmail.com"

RUN apt-get update && apt-get install -y build-essential libarchive-dev

RUN conda install -c conda-forge mamba
RUN mamba create -n omnisci python=3.8
COPY requirements.txt .
RUN /bin/bash -c 'source activate omnisci && mamba install -c conda-forge pyomnisci && pip install -r requirements.txt'

COPY . /app
WORKDIR /app

