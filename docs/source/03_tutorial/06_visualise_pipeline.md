# Visualise pipelines

[Kedro-Viz](https://github.com/quantumblacklabs/kedro-viz) displays data and machine-learning pipelines in an informative way, emphasising the connections between datasets and nodes. It shows the structure of your Kedro pipeline. This exercise assumes that you have been following the [Spaceflights tutorial](01_spaceflights_tutorial.md).

## Install Kedro-Viz

You can install Kedro-Viz by running:
```bash
pip install kedro-viz
```

## Visualise a whole pipeline

You should be in your project root directory, and once Kedro-Viz is installed you can visualise your pipeline by running:
```bash
kedro viz
```

This command will run a server on http://127.0.0.1:4141 that will open up your visualisation on a browser. You should
 be able to see the following:

![](../meta/images/pipeline_visualisation.png)

You may also use the `--autoreload` flag to autoreload Kedro Viz when a `Python` or `YAML` file has changed in the corresponding Kedro project.

![](../meta/images/pipeline_viz_autoreload.gif)

If a visualisation panel opens up and a pipeline is not visible then please check that your [pipeline definition](04_create_pipelines.md) is complete. All other errors can be logged as GitHub Issues on the [Kedro-Viz repository](https://github.com/quantumblacklabs/kedro-viz).

## Exit an open visualisation

You exit this visualisation by closing the open browser and entering **Ctrl+C** or **Cmd+C** in your terminal.

## Visualise layers

A pipeline can be broken up into different layers according to how data is processed, and using a convention for layers makes it easier to collaborate. For example, the [data engineering convention](../12_faq/01_faq.md#what-is-data-engineering-convention) shown here labels datasets according to the stage of the pipeline (e.g. whether the data has been cleaned).

Kedro-Viz makes it easy to visualise these data processing stages by adding a `layer` attribute to the datasets in the Data Catalog. We will be modifying `catalog.yml` with the following:

```yaml
companies:
  type: pandas.CSVDataSet
  filepath: data/01_raw/companies.csv
  layer: raw

reviews:
  type: pandas.CSVDataSet
  filepath: data/01_raw/reviews.csv
  layer: raw

shuttles:
  type: pandas.ExcelDataSet
  filepath: data/01_raw/shuttles.xlsx
  layer: raw

preprocessed_companies:
  type: pandas.CSVDataSet
  filepath: data/02_intermediate/preprocessed_companies.csv
  layer: intermediate

preprocessed_shuttles:
  type: pandas.CSVDataSet
  filepath: data/02_intermediate/preprocessed_shuttles.csv
  layer: intermediate

model_input_table:
  type: pandas.CSVDataSet
  filepath: data/03_primary/model_input_table.csv
  layer: primary

regressor:
  type: pickle.PickleDataSet
  filepath: data/06_models/regressor.pickle
  versioned: true
  layer: models
```

Run kedro-viz again with `kedro viz` and observe how your visualisation has changed to indicate the layers:

![](../meta/images/pipeline_visualisation_with_layers.png)

## Share a pipeline

Visualisations from Kedro-Viz are made shareable by using functionality that allows you to save the visualisation as a JSON file.

To save a visualisation, run:
```
kedro viz --save-file my_shareable_pipeline.json
```

This command will save a pipeline visualisation of your primary `__default__` pipeline as a JSON file called `my_shareable_pipeline.json`.

To visualise a saved pipeline, run:
```
kedro viz --load-file my_shareable_pipeline.json
```

And this will visualise the pipeline visualisation saved as `my_shareable_pipeline.json`.
