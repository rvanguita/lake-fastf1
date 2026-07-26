WITH year_driver_points AS (
SELECT 
    Year
    , DriverId
    , SUM(Points) as total_points
FROM results 
GROUP BY 
    Year
    , DriverId
ORDER BY 
    Year
    , total_points DESC
),

rn_year_driver AS (
SELECT 
    *
    , ROW_NUMBER() OVER (PARTITION BY Year ORDER BY total_points DESC) as rank_driver
FROM year_driver_points
)

SELECT
    *
FROM rn_year_driver
WHERE rank_driver = 1

