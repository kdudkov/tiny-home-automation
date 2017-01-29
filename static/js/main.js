
var json_url = '/items/';
var cmd_url = '/item/';
var reload_time = 5000;
var ws_reconnect_time = 5000;
var ws_url = 'ws://' + window.location.host + '/ws';
var ws = true;

app = angular.module('app', []);

app.filter('since', function () {
    return function (n, time) {
        var res = '';
        if (time) {
            n = new Date().getTime() / 1000 - n;
        }
        if (n < 0) return 'future';
        var h = Math.floor(n / 3600);
        if (h > 0) {
            res += h + 'h ';
            n = n % 3600;
        }
        var m = Math.floor(n / 60);
        if (m > 0) {
            res += m + 'm ';
            n = n % 60;
        }
        res += Math.floor(n) + 's';
        return res;
    }
});

app.controller('MainCtrl', function ($log, $scope, $http, $timeout) {

    get_data = function () {
        $http.get(json_url)
                .success(function (data) {
                        $scope.updated = new Date();
                        $scope.data = data;
                        var tags = new Set();
                        for (var item of data) {
                            if (item != null && item.hasOwnProperty("tags")) {
                                for (var ii of item.tags) {
                                    tags.add(ii);
                                }
                            }
                        }
                    var t = [];
                    tags.forEach(function (x) {
                        t.push(x);
                    });
                    $scope.tags = t;
                    $scope.tags.sort();
                    $scope.error_text = '';
                    if (! ws)
                        $timeout(get_data, reload_time);
                    $scope.set_tag($scope.tags[0]);
                    }
                )
                .error(function () {
                    $log.error('error getting data');
                    $scope.error_text = 'не могу получить данные с сервера';
                    $timeout(get_data, reload_time * 5);
                });
    };

    ws_connect = function() {
        socket = new WebSocket(ws_url);

        socket.onopen = function() {
          $log.info("Соединение установлено.");
        };

        socket.onclose = function(event) {
          if (event.wasClean) {
            $log.info('Closed clear');
          } else {
            $log.info('Socket dropped');
          }
          $log.info('Code: ' + event.code + ' reason: ' + event.reason);
          $timeout(ws_connect, ws_reconnect_time);
        };

        socket.onmessage = function(event) {
            var obj = JSON.parse(event.data);
            for (var item of $scope.data) {
                 if (item != null && item.name == obj.name) {
                        item.value = obj.value;
                        item._value = obj._value;
                        item.formatted = obj.formatted;
                        item.checked = obj.checked;
                        item.changed = obj.changed;
                        $scope.$apply();
                        break;
                 }
            }
        };
    };

    $scope.toggle_switch = function (item) {
        var cmd = 'Off';
        if (item._value == 'Off') {
            cmd = 'On';
        }
        $log.info('command ' + cmd + ' to ' + item.name);
        if (! ws) {
            item._value = cmd;
            item.value = cmd;
        }
        $scope.send(item, cmd);
    };

    $scope.add_val = function (item, val) {
        var new_val = item._value + val;
        if (! ws) {
            item.formatted = new_val;
            item._value = new_val;
            item.value = new_val;
        }
        $scope.send(item, new_val);
    };

    $scope.send = function(item, val) {
        if (ws) {
            socket.send($scope.current_tag + ';' + item.name + ';' + val)
        } else {
            $http.post(cmd_url + item.name, val)
                    .success(function (data) {
                        $log.info('ok ' + data);

                    })
                    .error(function () {
                        $log.error('error sending command to ' + item.name);
                    });
        }
    };

    $scope.set_tag = function (tag) {
        $log.info("set tag " + tag);
        $scope.current_tag = tag;
        if (ws)
            socket.send(tag);
    };

    $scope.has_tag = function (item) {
        if ($scope.current_tag == null) return true;
        if (item.hasOwnProperty("tags")) {
            for (var tag of item.tags) {
                if (tag == $scope.current_tag) return true;
            }
        }
        return false;
    };

    $scope.age = function (n, time) {
        var res = '';
        if (n == null || n == undefined) return '';
        if (time) {
            if (n <= 0) return '-';
            n = new Date().getTime() / 1000 - n;
        }
        if (n <= 0) return 'now';
        var h = Math.floor(n / 3600);
        if (h > 0) {
            res += h + 'ч ';
            n = n % 3600;
        }
        var m = Math.floor(n / 60);
        if (m > 0) {
            res += m + 'м ';
            n = n % 60;
        }
        res += Math.floor(n) + 'с';
        return res;
    };

    ws_connect();
    get_data();
});