/**
 * Created by powergx on 15/7/23.
 */
var http = require('http');
var rsa = require('./rsa.js');
var url = require("url");

http.createServer(function (req, res) {
    res.writeHead(200, {'Content-Type': 'text/plain'});

    var url_parts = url.parse(req.url, true);
    var query = url_parts.query;

    if(query.password == undefined || query.captcha == undefined || query.check_n == undefined || query.check_e == undefined ){
        console.log("参数错误");
        res.end('false');
        return;
    }
    try {
        var p = rsa.encrypt_c(query.password, query.captcha, query.check_n, query.check_e)
    }catch(e){
        console.log("加密失败");
        res.end('false');
        return;
    }

    res.end(p);
}).listen(9898, "0.0.0.0");