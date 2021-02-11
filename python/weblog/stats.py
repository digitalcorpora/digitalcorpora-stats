#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import os

def get_table(db_conn, interval):
    query = "SELECT downloadable.dirname, downloadable.basename, count(*) as " \
            "total_downloads FROM downloads LEFT JOIN downloadable on downloads.did " \
            "= downloadable.id  WHERE downloads.dtime >= now() - interval " \
            + interval + " group by downloadable.dirname, downloadable.basename order by total_downloads desc limit 10;"
    db_conn.execute(query)
    header = [i[0] for i in db_conn.description]
    rows = [list(i) for i in db_conn.fetchall()]
    rows.insert(0,header)
    return rows

def list_to_html(the_list):
    htable='<table>'
    for i, row in enumerate(the_list):
        if i == 0:
            tag = "th"
        else:
            tag = "td"
        newrow = '<tr>'
        for cell in row:
            newrow += ('<' + tag + '>' + str(cell) + '</' + tag + '>')
        newrow += '</tr>'
        htable += newrow
    htable += '</table>'
    return htable


conn = pymysql.connect(host="mysql.digitalcorpora.org",
    database="dcstats",
    user="dwriter",
    password="zruiuGfbMiNWtzM")
cursor = conn.cursor()

page_header = """<!DOCTYPE html> 
<html>
<head>

</head>
 
 <body>
 <style>
    .box{
        display: none;
    }
</style>
 
 <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
<script>
$(document).ready(function(){
    $('input[type="radio"]').click(function(){
        var inputValue = $(this).attr("value");
        var targetBox = $("." + inputValue);
        $(".box").not(targetBox).hide();
        $(targetBox).show();
    });
});
</script>
    <div>
        <label><input type="radio" name="colorRadio" value="day">Current Day</label>
        <label><input type="radio" name="colorRadio" value="week">Last 7 Days</label>
        <label><input type="radio" name="colorRadio" value="month">Last 30 Day</label>
        <label><input type="radio" name="colorRadio" value="all">All Time</label>
    </div>
    
    """

day_section = '<div class="day box">Current Day \n ' + list_to_html(get_table(cursor, "1 DAY")) + '</div>\n'
week_section = '<div class="week box">Last 7 Days \n ' + list_to_html(get_table(cursor, "1 WEEK")) + '</div>\n'
month_section = '<div class="month box">Current Day \n ' + list_to_html(get_table(cursor, "1 MONTH")) + '</div>\n'
all_section = '<div class="month box">All Time \n ' + list_to_html(get_table(cursor, "100 YEAR")) + '</div>\n'

page_footer = """
 </body>
 </html>
"""

webpage = page_header + day_section + week_section + month_section + all_section + page_footer

print(webpage)

