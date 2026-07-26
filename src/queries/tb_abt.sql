WITH tb_abt AS (
    
<<<<<<< HEAD
    SELECT *
=======
    SELECT t1.*
>>>>>>> etl
        , coalesce(t2.rank_driver, 0) AS flChampion

    FROM driver_all_statistic AS t1

    LEFT JOIN champions AS t2
    ON t1.DriverId = t2.DriverId
    AND year(t1.dt_ref) = t2.year

    WHERE t1.dt_ref BETWEEN 
    date('2000') AND date('2026')

    -- ORDER BY DriverId, dt_ref DESC
)

SELECT * FROM tb_abt