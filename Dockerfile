FROM continuumio/miniconda3:4.10.3
MAINTAINER Mingxun Wang "mwang87@gmail.com"

RUN apt-get update && apt-get install -y \
        build-essential \
        libarchive-dev

RUN conda install -c conda-forge mamba
RUN mamba create -n omnisci python=3.8
COPY requirements.txt .
RUN /bin/bash -c 'source activate omnisci && mamba install -c conda-forge \
                pyomnisci \
                gcc \
                gxx \
                libstdcxx-ng \
                pyarrow=3.0.0 \
                vaex=4.0.0 \
                vaex-core=4.0.0 \
                vaex-server=0.4.0 \
                "python-utils<=3.0.0" \
                "pydantic<2" \
                xarray && \
                pip install -r requirements.txt'

ENV LD_LIBRARY_PATH=/opt/conda/envs/omnisci/lib:$LD_LIBRARY_PATH

COPY . /app
WORKDIR /app

