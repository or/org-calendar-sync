function load(element_id) {
    var width;
    var height;
    var graph_element_id = element_id;
    var bar_size = 30;
    var bar_padding = 5;

    var svg = d3.select(graph_element_id)
        .append("svg");
    var legendLayer;
    var graph;
    var data;
    var displayTypes;
    var hideTypes = {};

    var hour = d3.timeFormat("%H:%M");
    var clickedEntry = null;

    var x = d3.scaleTime();
    var y = d3.scaleTime();
    var xGridScale = d3.scaleTime();
    var yGridScale = d3.scaleTime();

    var baseDate = new Date();

    var xAxis, yAxis;
    var xGrid, yGrid;

    var gX, gY;
    var gGx, gGy;

    var zoom;

    var buildXAxis = () => {
        if (gX !== undefined) {
            gX.remove();
        }

        var tickFrequency = 1;
        if (d3.event != null) {
            tickFrequency = Math.floor(Math.pow(2, 4 * (1 - d3.event.transform.k)));
            if (tickFrequency < 1) {
                tickFrequency = 1;
            } else if (tickFrequency > 14) {
                tickFrequency = 14;
            }
        }

        xAxis = d3.axisTop(x)
            .ticks(d3.timeDay.every(tickFrequency))
            .tickFormat((d) => {
                if (d < x.domain()[0] || d > x.domain()[1]) {
                    return "";
                }
                return d3.timeFormat("%a, %d %b")(d);
            });

        gX = svg.append("g")
            .attr("class", "axis axis--x")
            .attr("transform", "translate(0," + height + ")")
            .call(xAxis);

        gX.selectAll("text")
            .attr("y", 10)
            .attr("x", 9)
            .attr("dy", "-.7em")
            .attr("transform", "rotate(-90)")
            .style("text-anchor", "start");

        xGrid = d3.axisBottom(xGridScale)
            .tickSize(height)
            .ticks(d3.timeDay.every(tickFrequency))
					  .tickFormat("");

    };

    var zoomed = () => {
        graph.attr("transform", d3.event.transform);

        buildXAxis();
        gX.call(xAxis.scale(d3.event.transform.rescaleX(x)));
        gY.call(yAxis.scale(d3.event.transform.rescaleY(y)));
        gGx.call(xGrid.scale(d3.event.transform.rescaleX(xGridScale)));
        gGy.call(yGrid.scale(d3.event.transform.rescaleY(yGridScale)));
    };

    var div = d3.select("body").append("div")
        .attr("class", "tooltip")
        .style("opacity", 0);

    var resize = () => {
        var element = document.getElementById(graph_element_id.substring(1));
        width = element.clientWidth;
        height = element.clientHeight;

        svg.attr("width", width)
        .attr("height", height);
    };

    var timeline = {};

    var oldOnResize = d3.select(window).on("resize");

    var timeOffset = (t) => {
        var tmp = new Date(baseDate);
        tmp.setHours(t.getHours());
        tmp.setMinutes(t.getMinutes());
        return tmp;
    };

    var pickTypeColorMap = {
        calendar: d3.schemePaired[1],
        ops: d3.schemePaired[5],
        sprint: d3.schemePaired[3],
        extra: d3.schemePaired[7],
        unknown: d3.schemeCategory10[7]
    };
    var pickTypeColor = (d) => {
        return pickTypeColorMap[d];
    };

    var colorRange =  [
        "#1395ba",
        "#c02e1d",
        "#f16c20",
        "#ebc844",
        "#a2b86c",
        "#0d3c55",
    ];
    colorRange = colorRange.concat(d3.schemePastel1).concat(d3.schemePastel2);
    var colorIndex = 0;
    var colorMap = {};

    var pickColor = (d) => {
        var name = d.pretty;
        if (!(name in colorMap)) {
            colorMap[name] = colorIndex;
            colorIndex = (colorIndex + 1) % colorRange.length;
        }

        return colorRange[colorMap[name]];
    };

    d3.select(window).on("resize", () => {
        if (typeof(oldOnResize) != "undefined") {
            oldOnResize();
        }
        timeline.onResize();
    });

    timeline.onResize = () => {
        resize();
        timeline.update();
    };

    timeline.load = (path) => {
        console.log("load...");
        d3.json(path).then((rawData) => {
            console.log("received.");
            var typeMap = {};
            data = [];
            rawData.forEach((d) => {
                data = data.concat(d[1].map((e) => {
                    e.start = new Date(e.start);
                    e.end = new Date(e.end);
                    if (e.filename.includes("calendar") || e.path.includes("Meetings")) {
                        e.type = "calendar";
                    } else if (e.filename.includes("oncall") || e.tags.includes("ops")) {
                        e.type = "ops";
                    } else if (e.name.indexOf("tt.") !== -1) {
                        e.type = "ops";
                    } else if (e.path.includes("Tasks")) {
                        e.type = "sprint";
                    } else if (e.path.includes("Extra")) {
                        e.type = "extra";
                    } else if (e.name.indexOf("sim.") !== -1) {
                        e.type = "sprint";
                    } else {
                        e.type = "unknown";
                    }

                    typeMap[e.type] = true;

                    e.pretty = e.name.replace(/\[\[[^\]]*\]\[([^\]]*)\]\]/g, "$1");
                    e.pretty = e.pretty.replace(/^(TODO|DONE|CANCELLED) /, "");

                    return e;
                }));
            });
            data = data.filter((d) => {
                if (hour(d.start) == "00:00") {
                    return false;
                }
                return true;
            });

            displayTypes = Object.keys(typeMap);

            console.log(data.length);

            timeline.update();
        });
    };

    timeline.update = () => {
        if (data === null) {
            return;
        }

        var xRange = [
            d3.min(data, (d) => {
          	    return d3.timeDay.floor(d.start);
            }),
        	  d3.max(data, (d) => {
         		    return d3.timeDay.ceil(d.end);
            })
        ];

        var yRange = [new Date(baseDate), new Date(baseDate)];
        yRange[0].setHours(7);
        yRange[0].setMinutes(0);
        yRange[1].setHours(19);
        yRange[1].setMinutes(0);

        var timeline_width = (xRange[1] - xRange[0]) / 24 / 60 / 60 / 1000 * (bar_size + bar_padding);
        if (timeline_width < width) {
            timeline_width = width;
        }

        x
            .domain(xRange)
            .range([0, timeline_width]);

        y
            .domain(yRange)
            .range([0, height]);

        xGridScale
            .domain(xRange)
            .range([-(bar_size + bar_padding) / 2,
                    timeline_width - (bar_size + bar_padding) / 2]);
        yGridScale
            .domain(yRange)
            .range([0, height]);

        svg.selectAll("g").remove();

        legendLayer = svg
            .append("g")
            .attr("transform", "translate(20,20)");

        buildXAxis();
        yAxis = d3.axisLeft(y)
            .tickFormat(d3.timeFormat("%H:%M"));

        yGrid = d3.axisRight(yGridScale)
            .tickSize(width)
            .ticks(d3.timeHour.every(2))
					  .tickFormat("");

			  gGx = svg.append("g")
				    .attr("class","x grid")
				    .call(xGrid);

			  gGy = svg.append("g")
				    .attr("class","y grid")
				    .call(yGrid);

        gY = svg.append("g")
            .attr("class", "axis axis--y")
            .attr("transform", "translate(" + width + " ,0)")
            .call(yAxis);

        var minZoom = 0.1;
        zoom = d3.zoom()
            .scaleExtent([minZoom, 40])
            .translateExtent([[(-10 - width) / minZoom, -100 / minZoom],
                              [(timeline_width + width + 10) / minZoom, (height + 100) / minZoom]])
            .on("zoom", zoomed);

        graph = svg.append("g")
            .attr("class", "graph");

        timeline.updateData();
        svg.call(zoom);
    };

    timeline.updateData = () => {
        var filteredData = data.filter((d) => {
            if (hideTypes[d.type]) {
                return false;
            }
            return true;
        });

        graph
            .selectAll("rect").remove();

        graph
            .selectAll("rect")
            .data(filteredData)
            .enter()
            .append("rect")
            .attr("class", "times bar")
            .attr("x", (d) => {
                return x(d3.timeDay.floor(d.start)) - bar_size / 2;
            })
            .attr("y", (d) => {
                return y(timeOffset(d.start));
            })
            .attr("width", (d) => {
                return bar_size;
            })
            .attr("height", (d) => {
                return Math.max(0, y(timeOffset(d.end)) - y(timeOffset(d.start)));
            })
            .attr("rx", 3)
            .attr("ry", 3)
            .attr("stroke-width", 2)
            .attr("stroke", (d) => { return pickTypeColor(d.type); })
            .attr("fill-opacity", (d) => {
                if (d.pretty == clickedEntry) {
                    return 1;
                }
                return 0.3;
            })
            .attr("fill", pickColor)
            .on("mouseover", (d) => {
                div.transition()
                   .duration(200)
                   .style("opacity", 0.8);
                div.html(d.pretty + "<br/>" + d.type)
                   .style("left", (d3.event.pageX) + "px")
                   .style("top", (d3.event.pageY - 28) + "px");

                if (clickedEntry != d.pretty) {
                    clickedEntry = d.pretty;
                    graph.selectAll("rect").data(filteredData)
                        .attr("fill-opacity", (d) => {
                            if (d.pretty == clickedEntry) {
                                return 1;
                            }
                            return 0.3;
                        })
                    ;
                }
            })
            .on("mousemove", (d) => {
                div
                    .style("left", (d3.event.pageX) + "px")
                    .style("top", (d3.event.pageY - 28) + "px");
            })
            .on("mouseout", (d) => {
                div.transition()
                    .duration(500)
                    .style("opacity", 0);

                if (clickedEntry !== null) {
                    clickedEntry = null;
                    graph.selectAll("rect").data(filteredData)
                        .attr("fill-opacity", (d) => {
                            if (d.pretty == clickedEntry) {
                                return 1;
                            }
                            return 0.3;
                        })
                    ;
                }
            })
				;

        legendLayer.selectAll(".legend").remove();

        var legend = legendLayer.selectAll(".legend")
            .data(displayTypes)
            .enter()
            .append("g")
            .attr("class", "legend clickable")
            .on("click", (d) => {
                if (d in hideTypes) {
                    delete hideTypes[d];
                } else {
                    hideTypes[d] = true;
                }
                timeline.updateData();
            })
            .attr("transform", (d, i) => {
                var x = i * 100;
                var y = 0;
                return "translate(" + x + "," + y + ")";
            })
        ;

        legend
            .append("rect")
            .attr("class", "checkbox-edge")
            .attr("width", 16)
            .attr("height", 16)
            .attr("stroke", (d) => { return pickTypeColor(d); })
            .attr("stroke-width", 2)
            .attr("fill", "white")
        ;

        legend
            .append("rect")
            .attr("class", "checkbox")
            .attr("transform", "translate(2,2)")
            .attr("width", 12)
            .attr("height", 12)
            .attr("stroke-width", 0)
            .attr("fill", (d) => {
                if (d in hideTypes) {
                    return "white";
                }
                return pickTypeColor(d);
            })
        ;

        legend.append("text")
            .attr("x", 25)
            .attr("y", 9)
            .attr("dy", ".35em")
            .text((d) => { return d; })
        ;
    };

    resize();

    timeline.load("./timeline.json");

    return timeline;
}
