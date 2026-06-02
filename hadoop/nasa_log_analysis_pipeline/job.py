from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    regexp_extract, col, to_timestamp,
    when, desc, date_trunc
)

# Create spark session

spark = SparkSession.builder \
    .appName("NASA Log Analysis") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .getOrCreate()
spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")

# Load raw logs

logs_df = spark.read.text("hdfs:///user/logs/raw/")

# Apache log regex

log_pattern = r'^(\S+) \S+ \S+ \[(.*?)\] "(\S+) (\S+) \S+" (\d{3}) (\S+)'

parsed_df = logs_df.select(
    regexp_extract("value", log_pattern, 1).alias("host"),
    regexp_extract("value", log_pattern, 2).alias("timestamp"),
    regexp_extract("value", log_pattern, 3).alias("method"),
    regexp_extract("value", log_pattern, 4).alias("url"),
    regexp_extract("value", log_pattern, 5).alias("response_code"),
    regexp_extract("value", log_pattern, 6).alias("bytes")
)

# Filter malformed rows

clean_df = parsed_df.filter(col("host") != "")

# Cast types

clean_df = clean_df.withColumn(
    "timestamp",
    to_timestamp(col("timestamp"), "dd/MMM/yyyy:HH:mm:ss Z")
).withColumn(
    "response_code",
    col("response_code").cast("int")
).withColumn(
    "bytes",
    when(col("bytes") == "-", 0).otherwise(col("bytes").cast("int"))
)

# Aggregations

# Top 10 urls
top_urls_df = clean_df.groupBy("url") \
    .count() \
    .orderBy(desc("count")) \
    .limit(10)
# Requests per hour
hourly_df = clean_df.groupBy(
    date_trunc("hour", col("timestamp")).alias("hour")
).count().orderBy("hour")
# Error counts (4xx, 5xx)
errors_df = clean_df.filter(col("response_code") >= 400) \
    .groupBy("response_code") \
    .count()

# Write output to hdfs

top_urls_df.write.mode("overwrite") \
    .parquet("hdfs:///user/logs/output/top_urls")

hourly_df.write.mode("overwrite") \
    .parquet("hdfs:///user/logs/output/hourly_traffic")

errors_df.write.mode("overwrite") \
    .parquet("hdfs:///user/logs/output/errors")

spark.stop()