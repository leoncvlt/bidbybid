# bidbybid

A python tool which scrapes sold eBay auctions based on one (or more) search terms, and compiles minimum, maximum and average sold prices across a time period.

## Installation & Requirements

Make sure you're in your virtual environment of choice, then run
- `poetry install --no-dev` if you have [Poetry](https://python-poetry.org/) installed
- `pip install -r requirements.txt` otherwise

## Usage
```
bidbybid.py [-h] [-l {en_US,en_UK}] [-a] [-b ANOMALIES_BIAS] [-c] [-v] search

positional arguments:
  search                The ebay search terms. Supports advanced patterns such as '-' to exclude words, parentheses for OR queries, '*' as wildcards and quotes for literals. For more information, 
                        see https://www.thebalancesmb.com/mastering-ebay-search-for-sellers-2531709

optional arguments:
  -h, --help            show this help message and exit
  -l {en_US,en_UK}, --locale {en_US,en_UK}
                        The locale to run the search in - will set the eBay's country domain and currency / dates parsing.
  -a, --exclude-anomalies
                        Excludes auctions which strays
  -b ANOMALIES_BIAS, --anomalies-bias ANOMALIES_BIAS
                        Bias for excluding anomalies(e.g. a bias of 0.25 will exclude any auctions which sold at 25% less or more than the average sold price).Only applicaple with --exclude-anomalies. Default is 0.5
  -c, --chart           Displays the scraped results in chart
  -v, --verbose         Increase output log verbosity
```

## Sample usage
```
python bidbybid.py "xenoblade 2 -collector -special -edition -controller -figure"
```
Get the prices for the videogame Xenoblade 2, excluding special editions and bundles.

```
python bidbybid.py "thinkpad x220, thinkpad x230, thinkpad x240, thinkpad x250, thinkpad x260" -a -c 
```
Get the prices for different models of Thinkpad laptops, excluding any auction that strays more than 50% from the average price (to filter out likely auctions for parts or broken items), and display the results in a chart.

## To do
[ ] Add more ebay locales
[ ] Implement chart functionality with `matplotlib`
    [ ] Add polynomial fit to display trendlines for the prices

## Support [![Buy me a coffee](https://img.shields.io/badge/-buy%20me%20a%20coffee-lightgrey?style=flat&logo=buy-me-a-coffee&color=FF813F&logoColor=white "Buy me a coffee")](https://www.buymeacoffee.com/leoncvlt)
If this tool has proven useful to you, consider [buying me a coffee](https://www.buymeacoffee.com/leoncvlt) to support development of this and [many other projects](https://github.com/leoncvlt?tab=repositories).