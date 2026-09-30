let
    Source = Lakehouse.Contents([HierarchicalNavigation = null, EnableVorder = true, OutputMetadataRefresh = true]),
    #"Navigation 1" = Source{[workspaceId = "."]}[Data],
    #"Navigation 2" = #"Navigation 1"{[lakehouseName = "lh_kcorp_plant"]}[Data],
    #"Navigation 3" = #"Navigation 2"{[Id = "bronze.dim_plant", ItemKind = "Table"]}[Data],
    #"Choose columns" = Table.SelectColumns(#"Navigation 3", {"PlantKey", "PlantCode", "PlantName", "Country", "Region", "PlantType", "PlantManager"}),
    #"Trimmed text" = Table.TransformColumns(#"Choose columns", {{"PlantCode", Text.Trim, type text}, {"PlantName", Text.Trim, type text}, {"Country", Text.Trim, type text}, {"Region", Text.Trim, type text}, {"PlantType", Text.Trim, type text}, {"PlantManager", Text.Trim, type text}}),
    #"Uppercased text" = Table.TransformColumns(#"Trimmed text", {{"PlantCode", Text.Upper, type text}}),
    #"Changed column type" = Table.TransformColumnTypes(#"Uppercased text", {{"PlantKey", Int64.Type}})
in
    #"Changed column type"
