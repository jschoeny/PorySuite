# Use version 22.04 of Ubuntu as the base image
FROM ubuntu:22.04

# Set the default values for the repository and tag arguments
ARG repo=https://github.com/pret/pokeemerald
ARG tag=latest

# Set the working directory to /root
WORKDIR /root

# Update the package lists and install necessary packages
RUN apt-get update && apt-get install -y --fix-missing wget git
RUN apt-get update && apt-get install -y --fix-missing build-essential binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi
RUN apt-get update && apt-get install -y --fix-missing libpng-dev gdebi-core

# Clone the specified repository into the 'src' directory
RUN git clone ${repo} src

# Clone the agbcc repository and build it
RUN git clone https://github.com/pret/agbcc agbcc
RUN cd agbcc && \
    ./build.sh

# Make sure the project compiles correctly
# Helps prevent building a Docker image with a broken environment
RUN cd agbcc && \
    ./install.sh ../src
RUN cd src && \
    make

# Remove the 'src' directory
RUN rm -rf src

# Create a 'projects' directory
RUN mkdir projects
