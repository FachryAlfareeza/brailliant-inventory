# Container version of the scan API, for ECS Fargate in the AWS Academy lab
# (the lab doesn't allow Lambda). Same app.py, run by src/server.py on port 8080.
FROM public.ecr.aws/docker/library/python:3.13-slim
RUN pip install --no-cache-dir pillow boto3
WORKDIR /app
COPY src/app.py src/s3_table.py src/server.py ./
EXPOSE 8080
CMD ["python", "server.py"]
